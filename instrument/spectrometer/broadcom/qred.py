import logging
import usb.core
import usb.util
from enum import Enum

import struct

import time

VENDOR_ID = 0x276e
PRODUCT_ID = 0x0209

class MsgType(Enum):
	COMMAND = 0x00
	PARAMETER = 0x01
	PROPERTY = 0x02
	VALUE = 0x03
	DATA = 0x04

class MsgKind(Enum):
	MSG_GET = 0x00
	MSG_SET = 0x01
	MSG_MIN = 0x02
	MSG_MAX = 0x03
	MSG_DEF = 0x04
	MSG_TYPE = 0x08
	MSG_NAME = 0x09
	MSG_UNIT = 0x0A
	MSG_LENGTH = 0x0F

class MsgCommand(Enum):
	CMD_INIT = 0x00
	CMD_BYE = 0x01
	CMD_SYS_RESET = 0x02
	CMD_PARAM_RESET = 0x03
	CMD_START_EXPOSURE = 0x04
	CMD_STOP_EXPOSURE = 0x05

class MsgMeasurementValueRequest(Enum):
	VAL_STATUS = 0x00
	VAL_SENSOR_TEMP = 0x01
	VAL_IO_PORT = 0x02
	VAL_SYSTICK = 0x03
	VAL_REMAINING_EXPOSURES = 0x04
	VAL_BUFFER_COUNT = 0x05
	VAL_SINK_TEMP = 0x06
	VAL_ANALOG_IN = 0x07
	VAL_TEC_STATUS = 0x08 #0 - cooling disabled, 1 - setpoint reached, 2 - approaching, please wait, 3 - not able to reach, 5 - sink too hot
	VAL_COOLING_CURRENT = 0x09
	VAL_CAL_WARNING = 0x0A
	VAL_VOLTAGE_SUPPLY = 0x0B
	VAL_VOLTAGE_USB = 0x0C
	VAL_VOLTAGE_AUX = 0x0D
	VAL_AUX_OVERCURRENT = 0x0E
	VAL_COOLING_CURRENT_MAX = 0x0F
	VAL_DEBUG_VAL = 0x10 # -274.4354
	VAL_POWER_PATH_TEMP = 0x11

class MsgBulkDataType(Enum):
	SPECTRUM = 0x00 #R
	WAVELENGTHS = 0x01 #R
	CAL_DATA = 0x02 #RW
	USER_DATA = 0x03 #RW
	AUX_INTERFACE = 0x04 #RW
	WAVELENGTH_COEFFS = 0x05
	NONLINEARITY_COEFFS = 0x06

class MsgDevicePropertyRequest(Enum):
	DEVICE_ID = 0x00
	SERIAL_NO = 0x01
	MANUFACTURER = 0x02
	MODEL = 0x03
	HW_VERSION = 0x04
	SW_VERSION = 0x05
	SPECTRUM_PEAK_VALUE = 0x06
	PIXEL_COUNT = 0x07
	DATA_COUNT = 0x08
	OFFSET_PIXEL_FIRST = 0x09
	OFFSET_PIXEL_COUNT = 0x0A
	DARK_PIXEL_FIRST = 0x0B
	DARK_PIXEL_COUNT = 0x0C
	REAL_PIXEL_FIRST = 0x0D
	PIXELS_PER_BIN_EXPONENT = 0x0E
	MIRROR_SPECTRUM = 0x0F
	SENSOR_TYPE = 0x10
	OPTICAL_CONFIG = 0x11
	BAD_PIXELS0 = 0x16
	BAD_PIXELS1 = 0x17
	BAD_PIXELS2 = 0x18
	BAD_PIXELS3 = 0x19
	PAGE_COUNT_CAL_DATA = 0x1A
	PAGE_COUNT_USER_DATA = 0x1B
	READOUT_NOISE = 0x1C

class MsgDeviceParameter(Enum):
	EXPOSURE_TIME = 0x00
	AVERAGING = 0x01
	PROCESSING_STEPS = 0x02
	CONFIG_IO = 0x03
	CONFIG_TRIGGER = 0x04
	TRIGGER_DELAY = 0x05
	TRIGGER_ENABLE_EXTERNAL = 0x06
	BAUDRATE = 0x07 #uint value of desired baudrate
	TURN_OFF_LEDS = 0x08
	PULSE_PERIOD = 0x09
	TEMP_TARGET = 0x0A # float 'C value
	TEMP_ENABLE_CONTROL = 0x0B
	SAMPLE_CLOCK_DELAY = 0x0C
	SENSOR_GAIN = 0x0D
	ANALOG_OUT = 0x0E
	TEMP_LIMIT_SINK = 0x0F # float 'C value

class MsgReturnCode(Enum):
	OK = 0x00
	UNKNOWN_COMMAND = 0x01
	INVALID_PARAMETER = 0x02
	MISSING_PARAMETER = 0x03
	INVALID_OPERATION = 0x04
	NOT_SUPPORTED = 0x05
	INVALID_PASSCODE = 0x06
	COMMUNICATION_ERROR = 0x07
	INTERNAL_ERROR = 0x08
	UNKNOWN_BOOTLOADER_COMMAND = 0x09

class TECStatus(Enum):
	DISABLED = 0x00
	SETPOINT_REACHED = 0x01
	APPROACHING = 0x02
	UNABLE_TO_REACH = 0x03
	SINK_TOO_HOT = 0x05

class Spectrometer:
	log = None
	_dev = None
	_ep_out = None
	_ep_in = None
	__max_rx_data_length = 16384
	_wl_coeffs = None
	_non_lin_coeffs = None
	_pixel_count = 0
	_wavelengths = None
	_exp_time_min = 0
	_exp_time_max = 0
	_averaging_min = 0
	_averaging_max = 0

	def __init__(self) -> None:
		super().__init__()
		self.log = logging.getLogger('Qred')
		self._dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
		if self._dev is None:
			self.log.error('Could not find Qred device')
			raise ValueError('Device not found')
			return
		self._dev.set_configuration()
		cfg = self._dev.get_active_configuration()
		comms_interface = cfg[(0, 0)]

		self._ep_out = usb.util.find_descriptor(
			comms_interface,
			# match the first OUT endpoint
			custom_match= \
				lambda e: \
					usb.util.endpoint_direction(e.bEndpointAddress) == \
					usb.util.ENDPOINT_OUT)

		self._ep_in = usb.util.find_descriptor(
			comms_interface,
			# match the first IN endpoint
			custom_match= \
				lambda e: \
					usb.util.endpoint_direction(e.bEndpointAddress) == \
					usb.util.ENDPOINT_IN)
		self._send_init()
		self.get_pixel_count()
		self.get_wavelength_mapping()
		self.get_exposure_time_min_us()
		self.get_exposure_time_max_us()
		self.get_averaging_min()
		self.get_averaging_max()

	def get_device_id(self):
		return self._read_and_unpack_int_prop(MsgDevicePropertyRequest.DEVICE_ID)

	def get_serial_number(self):
		return self._read_and_unpack_string_prop(MsgDevicePropertyRequest.SERIAL_NO)

	def get_manufacturer(self):
		return self._read_and_unpack_string_prop(MsgDevicePropertyRequest.MANUFACTURER)

	def get_device_name(self):
		return self._read_and_unpack_string_prop(MsgDevicePropertyRequest.MODEL)

	def get_hw_version(self):
		v = self._read_property(MsgDevicePropertyRequest.HW_VERSION)
		return '%d.%d.%d.%d' % (v[3], v[2], v[1], v[0])

	def get_sw_version(self):
		v = self._read_property(MsgDevicePropertyRequest.SW_VERSION)
		return '%d.%d.%d.%d' % (v[3], v[2], v[1], v[0])

	def get_sensor_type(self):
		return self._read_and_unpack_int_prop(MsgDevicePropertyRequest.SENSOR_TYPE)

	def get_pixel_count(self):
		if self._pixel_count == 0:
			self._pixel_count = self._read_and_unpack_int_prop(MsgDevicePropertyRequest.PIXEL_COUNT)
		return self._pixel_count

	def get_exposure_time_ms(self):
		return self.get_exposure_time_us() / 1000

	def get_exposure_time_us(self):
		return self._read_and_unpack_int_param(MsgDeviceParameter.EXPOSURE_TIME)

	def get_exposure_time_min_us(self):
		if self._exp_time_min == 0:
			self._exp_time_min = self._read_and_unpack_int_param(MsgDeviceParameter.EXPOSURE_TIME, msg_kind=MsgKind.MSG_MIN)
		return self._exp_time_min

	def get_exposure_time_max_us(self):
		if self._exp_time_max == 0:
			self._exp_time_max = self._read_and_unpack_int_param(MsgDeviceParameter.EXPOSURE_TIME, msg_kind=MsgKind.MSG_MAX)
		return self._exp_time_max

	def set_exposure_time_ms(self, value):
		et_us = value * 1000
		if et_us > self._exp_time_max:
			self.log.error('Exposure time of %d us is larger than allowed maximum of %d us', et_us, self._exp_time_max)
			raise ValueError('New exposure time too large')
		if et_us < self._exp_time_min:
			self.log.error('Exposure time of %d us is less than allowed minimum of %d us', et_us, self._exp_time_min)
			raise ValueError('New exposure time too small')
		self._write_int_to_reg(format_message(MsgType.PARAMETER, MsgKind.MSG_SET, MsgDeviceParameter.EXPOSURE_TIME), et_us)

	def get_averaging(self):
		return self._read_and_unpack_int_param(MsgDeviceParameter.AVERAGING, msg_kind=MsgKind.MSG_GET)

	def get_averaging_min(self):
		if self._averaging_min == 0:
			self._averaging_min = self._read_and_unpack_int_param(MsgDeviceParameter.AVERAGING, msg_kind=MsgKind.MSG_MIN)
		return self._averaging_min

	def get_averaging_max(self):
		if self._averaging_max == 0:
			self._averaging_max = self._read_and_unpack_int_param(MsgDeviceParameter.AVERAGING, msg_kind=MsgKind.MSG_MAX)
		return self._averaging_max

	def get_sensor_temp(self):
		return unpack_float(self._read_value(MsgMeasurementValueRequest.VAL_SENSOR_TEMP))

	def get_sink_temp(self):
		return unpack_float(self._read_value(MsgMeasurementValueRequest.VAL_SINK_TEMP))

	def get_wavelength_coefficients(self):
		raw = self._read_bulk_data(MsgBulkDataType.WAVELENGTH_COEFFS)
		self._wl_coeffs = struct.unpack('<4f', raw)
		return self._wl_coeffs

	def get_nonlinearity_coefficients(self):
		raw = self._read_bulk_data(MsgBulkDataType.NONLINEARITY_COEFFS)
		coeff_count = struct.unpack('<I', raw[:4])
		self._non_lin_coeffs = struct.unpack('<%sf' % coeff_count, raw[4:])
		return self._non_lin_coeffs

	def get_wavelength_mapping(self):
		if not self._wavelengths:
			raw_data = self._read_bulk_data(MsgBulkDataType.WAVELENGTHS)
			self._wavelengths = struct.unpack('<%df' %self.get_pixel_count(), raw_data)
		return self._wavelengths

	def get_cooling_current(self):
		return unpack_float(self._read_value(MsgMeasurementValueRequest.VAL_COOLING_CURRENT))

	def get_supply_voltage(self):
		return unpack_float(self._read_value(MsgMeasurementValueRequest.VAL_VOLTAGE_SUPPLY))

	def get_usb_voltage(self):
		return unpack_float(self._read_value(MsgMeasurementValueRequest.VAL_VOLTAGE_USB))

	# it seems that if temperature is not reachable within 10 seconds, Qred returns UNABLE_TO_REACH status
	def get_tec_status(self):
		return TECStatus(unpack_int(self._read_value(MsgMeasurementValueRequest.VAL_TEC_STATUS)))

	def get_target_temp(self):
		return unpack_float(self._read_parameter(MsgDeviceParameter.TEMP_TARGET))

	def set_target_temp(self, temp: float):
		self.log.info("Setting temperature to %3.6f", temp)
		return self._write_float_to_reg(format_message(MsgType.PARAMETER, MsgKind.MSG_SET, MsgDeviceParameter.TEMP_TARGET), temp)

	def get_available_spectra_count(self):
		return unpack_int(self._read_value(MsgMeasurementValueRequest.VAL_STATUS)) >> 8

	# negative count starts continuous mode
	# it looks like new exposure clears FIFO of all previous spectra. Tried sequence 1-5-1 and in spectra count I get the same numbers
	def start_exposure(self, count=1, continuous=False):
		if continuous:
			count = -1
		self._write_int_to_reg(format_message(MsgType.COMMAND, MsgKind.MSG_GET, MsgCommand.CMD_START_EXPOSURE), count)

	def get_spectrum(self):
		response = self._read_bulk_data(MsgBulkDataType.SPECTRUM)
		spectrum = Spectrum.parse_bytes(response)
		return spectrum

	def terminate(self):
		self._write_register(format_message(MsgType.COMMAND, MsgKind.MSG_GET, MsgCommand.CMD_BYE))
		usb.util.dispose_resources(self._dev)

	def _send_init(self):
		msg = format_message(MsgType.COMMAND, MsgKind.MSG_GET, MsgCommand.CMD_INIT)
		resp = self._read_register(msg)
		return resp

	def _read_and_unpack_int_param(self, param: MsgDeviceParameter, msg_kind:MsgKind=MsgKind.MSG_GET):
		return unpack_int(self._read_parameter(param, msg_kind))

	def _read_and_unpack_string_prop(self, prop: MsgDevicePropertyRequest):
		return unpack_decode_string(self._read_property(prop))

	def _read_and_unpack_int_prop(self, prop: MsgDevicePropertyRequest):
		return unpack_int(self._read_property(prop))

	def _read_property(self, prop: MsgDevicePropertyRequest):
		return self._read_register(format_message(MsgType.PROPERTY, MsgKind.MSG_GET, prop))

	def _read_parameter(self, param: MsgDeviceParameter, msg_kind:MsgKind=MsgKind.MSG_GET):
		return self._read_register(format_message(MsgType.PARAMETER, msg_kind, param))

	def _read_value(self, val: MsgMeasurementValueRequest):
		return self._read_register(format_message(MsgType.VALUE, MsgKind.MSG_GET, val))

	def _read_bulk_data(self, param: MsgBulkDataType):
		return self._read_register(format_message(MsgType.DATA, MsgKind.MSG_GET, param))

	def _write_int_to_reg(self, reg, value):
		packed = struct.pack('<Ii', reg, value)
		self._write_bus(packed)

	def _write_float_to_reg(self, reg, value):
		packed = struct.pack('<If', reg, value)
		self._write_bus(packed)

	def _read_register(self, reg):
		self._write_register(reg)
		# self._ep_out.write(data)
		resp = self._read_bus()
		status = MsgReturnCode(unpack_int(resp[:4]))
		if status is not MsgReturnCode.OK:
			self.log.error('Response to request %s was %s', reg, status.name)
		if (len(resp) <= 4) and (reg != 0x00):
			self.log.warning('Received too few bytes, retrying')
			time.sleep(1)
			return self._read_register(reg)
		return resp[4:]

	def _write_register(self, reg):
		data = struct.pack('<I', reg)
		self._write_bus(data)

	def _write_bus(self, data):
		self.log.debug('>: [{}]'.format(','.join(hex(x) for x in data)))
		self._ep_out.write(data)

	def _read_bus(self):
		resp = self._ep_in.read(self.__max_rx_data_length)
		self.log.debug('<: [{}]'.format(','.join(hex(x) for x in resp)))
		return resp


class Spectrum:
	header = None
	amplitudes = []  # The spectrum as a float array

	@classmethod
	def parse_bytes(cls, data_bytes):
		inst = cls()
		inst.header = Spectrum.SpectrumHeader.parse_bytes(data_bytes[:48])
		inst.amplitudes = struct.unpack('<%df' %inst.header.pixel_count, data_bytes[48:])
		return inst

	class SpectrumHeader:
		class SpectrometerUnits(Enum):
			UNKNOWN = 0
			ADC_VALUES = 1
			ADC_NORMALIZED = 2
			nWnm = 3
			nWm2nm = 4
			Wsrm2nm = 5
			Wsrnm = 6

		exposure_time = float
		averaging = 1
		timestamp = 0
		load_level = -1.0
		temperature = -300.0
		applied_processing = 0
		unit = SpectrometerUnits.UNKNOWN
		saturation_value = -1.0
		average_offset = 0.0
		average_dark = 0.0
		noise_level = -1.0
		pixel_count = 0
		pixel_format = 0

		@classmethod
		def parse_bytes(cls, data_bytes):
			inst = cls()
			# SPECTRUM_HEADER:
			#  0 int ExposureTime   # in us
			#  4 int Avaraging
			#  8 uint Timestamp     # in 1 ms units, start of exposure
			# 12 float LoadLevel
			# 16 float Temperature  # in degree Celcius
			# 20 uint16_t PixelCount
			# 22 uint16_t PixelFormat       # see below
			# 24 uint16_t ProcessingSteps   # applied processing steps
			# 26 uint16_t IntensityUnit
			# 28 int Spectrum Dropped   # not implemented
			# 32 float SaturationValue
			# 36 float OffsetAvg
			# 40 float DarkAvg
			# 44 float ReadoutNoise
			inst.exposure_time, inst.averaging, inst.timestamp, inst.load_level, inst.temperature, inst.pixel_count, \
			inst.pixel_format,	inst.applied_processing, inst.unit, dummy, inst.saturation_value, inst.average_offset, \
			inst.average_dark, inst.noise_level = struct.unpack('<iiIffHHHHiffff', data_bytes[:48])
			inst.unit = Spectrum.SpectrumHeader.SpectrometerUnits(inst.unit)
			return inst


def format_message(msgt :MsgType, msgk :MsgKind, body):
	return msgt.value << 12 | msgk.value << 8 | body.value

def unpack_decode_string(byte_arr):
	s, = struct.unpack('<%ds' % len(byte_arr), byte_arr)
	return s.decode('ascii')

def unpack_int(byte_arr):
	i, = struct.unpack('<I', byte_arr)
	return i

def unpack_float(byte_arr):
	f, = struct.unpack('<f', byte_arr)
	return f

def unpack_bool(byte_arr):
	# bools are still sent as ints
	int_val = unpack_int(byte_arr)
	return int_val != 0
