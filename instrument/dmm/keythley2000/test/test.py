import logging
import time

from devices.instrument.dmm.keythley2000 import keythley2000
from devices.instrument.dmm.keythley2000.keythley2000 import KEYTHLEY_2000_GPIB_ADDRESS
from devices.interface.gpib import prologix

log = logging.getLogger('test')
logging.basicConfig(level=logging.DEBUG)

gpib = prologix.GPIB_Controller('COM4')

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
	dmm.set_measurement_type(keythley2000.dmm.MeasType.VOLTAGE_DC)
	print(dmm.read_channel(1))
	time.sleep(1)
	dmm.set_measurement_type(keythley2000.dmm.MeasType.RESISTANCE)
	print(dmm.read_channel(2))
	time.sleep(1)
	dmm.set_measurement_type(keythley2000.dmm.MeasType.VOLTAGE_DC)
	print(dmm.read_channel(10))
	time.sleep(5)

gpib.close()