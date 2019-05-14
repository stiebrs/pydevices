from enum import Enum

KEYTHLEY_2000_GPIB_ADDRESS = 16

class dmm:
	class MeasType(Enum):
		VOLTAGE_DC = 'VOLT:DC'
		RESISTANCE = 'RES'

	def __init__(self, ser_read, ser_write) -> None:
		super().__init__()
		self._write = ser_write
		self._read = ser_read
		self._write('*RST')

	def _exchange(self, out, in_size):
		self._write(out)
		response = self._read(in_size)
		return response

	def get_device_id_string(self):
		return self._exchange('*IDN?', 100)

	def reset(self):
		self._write('*RST')

	def disable_beeper(self):
		self._write(':SYSTEM:BEEP:STATE 0')

	def set_measurement_type(self, mtype:MeasType):
		self._write(":SENS:FUNC '%s'" %mtype.value)

	def read_value(self):
		return float(self._exchange(':read?', 100))

	def read_channel(self, channel:int):
		if not (1 <= channel <= 10):
			raise ValueError('Wrong channel')
		return float(self._exchange(':route:close (@%d); :read?' % channel, 100))

