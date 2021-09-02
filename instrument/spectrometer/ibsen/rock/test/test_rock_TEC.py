import logging

from serial import Serial, time

from devices.instrument.spectrometer.ibsen.rock.rock import TECController

logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)

try:
	s = Serial('/dev/ttyUSB0', baudrate=115200)
	s.timeout = 0.2
	tec = TECController(s.read, s.write)
	print('Current temperature: {}\'C'.format(tec.read_temp()))
	# for whatever reason factory settings return 6?
	# print('Sensor type: {}'.format(tec.get_sensor_type()))
	print('TEC type: {}'.format(tec.get_tec_type()))
	tec.turn_TEC_on()
	while 1:
		try:
			print('Current temperature: {}\'C'.format(tec.read_temp()))
			time.sleep(1)
		except KeyboardInterrupt:
			break
	tec.turn_TEC_off()
finally:
	s.close()

