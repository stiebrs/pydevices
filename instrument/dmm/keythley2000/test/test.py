import logging
import time

from instrument.dmm.keythley2000 import keythley2000
from instrument.dmm.keythley2000.keythley2000 import KEYTHLEY_2000_GPIB_ADDRESS
from interface.gpib import prologix

if __name__ == '__main__':

	# log = logging.getLogger('test')
	# logging.basicConfig(level=logging.DEBUG)

	gpib = prologix.GPIB_Controller('/dev/ttyUSB1')

	gpib.set_mode(prologix.GPIB_Controller.OpMode.CONTROLLER)
	gpib.set_auto_get_response(False)
	gpib.set_eos(prologix.GPIB_Controller.EOS.NONE)
	gpib.set_target_address(KEYTHLEY_2000_GPIB_ADDRESS)
	gpib.send_data('++clr')
	time.sleep(0.1)
	dmm = keythley2000.dmm(gpib.read_response, gpib.send_data)
	dmm.disable_beeper()
	print(dmm.get_device_id_string())
	time.sleep(1)

	while(1):
		# if using rear input with multiplexing:
		# print(dmm.read_channel(1))
		# time.sleep(1)
		# dmm.set_measurement_type(keythley2000.dmm.MeasType.RESISTANCE)
		# print(dmm.read_channel(2))
		# time.sleep(1)
		# dmm.set_measurement_type(keythley2000.dmm.MeasType.VOLTAGE_DC)
		# print(dmm.read_channel(10))
		# time.sleep(5)

		# front input is not multiplexed, so no need to switch relays
		dmm.set_measurement_type(keythley2000.dmm.MeasType.VOLTAGE_DC)
		print(dmm.read_value())
		time.sleep(1)

	gpib.close()
