import logging
import serial
import time
from enum import Enum


class GPIB_Controller:
	_port = None
	_log = None

	class OpMode(Enum):
		DEVICE = 0x00
		CONTROLLER = 0x01

	class EOS(Enum):
		CRLF = 0x00
		CR = 0x01
		LF = 0x02
		NONE = 0x03


	def __init__(self, port) -> None:
		super().__init__()
		self._port = serial.Serial(port)
		self._port.timeout = 0.5
		self._log = logging.getLogger('GPIB')

	def send_data(self, data):
		# must escape '++' and CR/LF
		data = data + '\n'
		out_buffer = data.encode(encoding='ascii')
		self._log.debug('>: %s', out_buffer)
		self._port.write(out_buffer)

	def read_response(self, expected_size):
		self.send_data('++read eoi')
		response = self._port.read(expected_size)
		self._log.debug('<: %s', response)
		# remove trailing newline
		return response[:len(response)-1].decode('ascii')

	def exchange(self, out, expected_response_size):
		self.send_data(out)
		return self.read_response(expected_response_size)

	def set_target_address(self, address):
		self.send_data('++addr ' + str(address))

	def set_mode(self, mode: OpMode):
		self.send_data('++mode ' + str(mode.value))

	# bool whether GPIB controller should automatically query the instrument after issuing write command
	def set_auto_get_response(self, auto:bool):
		self.send_data('++auto ' + str(int(auto)))

	def set_eoi_assert(self, eoi:bool):
		self.send_data('++eoi ' + str(int(eoi)))

	def set_eos(self, eos:EOS):
		self.send_data('++eos ' + str(eos.value))

	def close(self):
		self._port.close()
