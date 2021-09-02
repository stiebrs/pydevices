import logging
from enum import Enum

ACK = 0x06
NAK = 0x15
BELL = 0x07


class BaudRates(Enum):
	BAUD_38400 = 384
	BAUD_115200 = 115
	BAUD_921000 = 921


class OutputFormat(Enum):
	HEX_BIG_ENDIAN = 1
	ASCII_W_SPACES = 2
	HEX_W_LEN_CHECKSUM = 3
	ASCII_W_LINES = 4
	HEX_LITTLE_ENDIAN = 5
	HEX_LITTLE_ENDIAN_W_LEN_CHECKSUM = 6
	ASCII_W_WAVELENGTH_LINES = 7


class CaptureType(Enum):
	DARK = 'DARK'
	LIGHT = 'LIGHT'
	SUBTRACTED = 'REFER'
	TRANSMISSION = 'TRANS'


class Spectrometer():
	def_char_count = 100
	_write_fn = None
	_read_fn = None
	_log = None
	pixel_count = 0
	_wl_coefficients = {
		'A': 0,
		'B1': 0,
		'B2': 0,
		'B3': 0,
		'B4': 0
	}

	def __init__(self, ser_read, ser_write) -> None:
		super().__init__()
		self._write_fn = ser_write
		self._read_fn = ser_read
		self._log = logging.getLogger('IbsenRock')
		self.reset()
		self._fill_wavelength_coeffs()

	def get_id(self):
		return self._exchange('IDN?')

	def get_version(self):
		return self._exchange('VERS?')

	def get_serial_number(self):
		return int(self._exchange_with_trim('PARA:SERN?'))

	def get_pixel_count(self):
		if self.pixel_count == 0:
			pc = int(self._exchange_with_trim('PARA:PIX?'))
			self.pixel_count = pc
		return self.pixel_count

	def get_baud_rate(self):
		return BaudRates(int(self._exchange_with_trim('PARA:BAUD?')))

	def get_integration_time(self):
		r = self._exchange('CONF:TINT?')
		# r is in format 'Previous tint:\t  500\rConfigured tint:\t  500\r'm we want just the last number
		r = r.split(':\t')[2].strip()
		return int(r)

	def get_pixel_to_wavelength_mapping(self):
		pixel_count = self.get_pixel_count()
		if self._wl_coefficients['A'] == 0:
			self._fill_wavelength_coeffs()
		p2wl = []
		for p in range(pixel_count):
			p2wl.append(
				self._wl_coefficients['A'] +
				self._wl_coefficients['B1'] * p +
				self._wl_coefficients['B2'] * p**2 +
				self._wl_coefficients['B3'] * p**3 +
				self._wl_coefficients['B4'] * p**4
			)
		return p2wl

	def _fill_wavelength_coeffs(self):
		self._wl_coefficients['A'] = float(self._exchange_with_trim('PARA:FIT0?'))
		self._wl_coefficients['B1'] = float(self._exchange_with_trim('PARA:FIT1?'))
		self._wl_coefficients['B2'] = float(self._exchange_with_trim('PARA:FIT2?'))
		self._wl_coefficients['B3'] = float(self._exchange_with_trim('PARA:FIT3?'))
		self._wl_coefficients['B4'] = float(self._exchange_with_trim('PARA:FIT4?'))

	def set_integration_time_ms(self, it):
		r = self._exchange('CONF:TINT {}'.format(it), 1)[0]
		if r == NAK:
			raise ValueError('Got NAK for setting integration time!')

	def reset(self):
		return self._exchange('RST')

	def capture(self, type, integration_time, average_count, format:OutputFormat):
		response = self._exchange('MEAS:{} {} {} {}'.format(type.value, integration_time, average_count, format.value), 1)
		if response[0] == '\x06':
			while 1:
				# wait for bell
				b = self._read_fn(1)
				if (b == b'\x07'):
					data = self._read_fn(6000)
					spec = [int(x) for x in data.split()]
					return spec
		else:
			raise ValueError('Got NAK on capture request')

	def fetch_last(self, type, format):
		data = self._exchange('FETCH:{} {}'.format(type.value, format.value), 6000)
		spec = [int(x) for x in data.split()]
		return spec

	def _exchange_with_trim(self, out, in_size=def_char_count):
		r = self._exchange(out, in_size)
		result = r.split(':\t')[1].strip()
		return result

	def _exchange(self, out, in_size=def_char_count):
		out = '*' + out + '\r'
		self._log.debug('>: %s', out)
		o = out.encode('ascii')
		self._write_fn(o)
		r = self._read_fn(in_size)
		self._log.debug('<: %s', r)
		response = r.decode('ascii').strip()
		return response


class TECController:
	def_char_count = 100
	_write_fn = None
	_read_fn = None
	_log = None

	class TECtype(Enum):
		SENSORS_UNLIMITED_LDB_1_STAGE = 0
		SENSORS_UNLIMITED_LDB_2_STAGE = 1
		SENSORS_UNLIMITED_LDB_3_STAGE = 2
		HAMAMATSU_S5930_512 = 3
		HAMAMATSU_S5930_256 = 4

	class TECsensorType(Enum):
		HAMAMATSU_ACTIVE = 0
		HAMAMATSU_PASSIVE = 1
		SENSORS_UNLIMITED_ACTIVE = 2
		SENSORS_UNLIMITED_PASSIVE = 3

	def __init__(self, ser_read, ser_write) -> None:
		super().__init__()
		self._write_fn = ser_write
		self._read_fn = ser_read
		self._log = logging.getLogger('IbsenRockTEC')

	def read_temp(self):
		return float(self._exchange_with_trim('para:tectemp?'))

	def get_sensor_type(self):
		return TECController.TECsensorType(int(self._exchange_with_trim('para:tecsen?')))

	def turn_TEC_on(self):
		return self._exchange('para:teccon {}'.format(2), 0)

	def turn_TEC_off(self):
		return self._exchange('para:teccon {}'.format(0), 0)

	def get_tec_type(self):
		return TECController.TECtype(int(self._exchange_with_trim('para:tectype?')))

	def _exchange_with_trim(self, out, in_size=def_char_count):
		r = self._exchange(out, in_size)
		result = r.split('\t')[1].strip()
		return result

	def _exchange(self, out, in_size=def_char_count):
		out = '*' + out + '\r'
		o = out.encode('ascii')
		self._log.debug('>: %s', out)
		self._write_fn(o)
		r = self._read_fn(100)
		self._log.debug('<: %s', r)
		if r[0] != 0x06:
			raise ValueError("Got NAK!")
		response = r[1:].decode('ascii').strip()
		return response
