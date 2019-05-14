#!/usr/bin/env python3
import logging

import sys

import time
from pprint import pprint

from devices.instrument.spectrometer.broadcom.qred import Spectrometer, TECStatus

if __name__ == '__main__':
	log = logging.getLogger('test')
	logging.basicConfig(level=logging.DEBUG)
	spec = Spectrometer()
	print('%s %s, SN: %s, ID: %s' % ( spec.get_manufacturer(), spec.get_device_name(), spec.get_serial_number(), hex(spec.get_device_id())))
	print('HW version: %s, SW version: %s' % (spec.get_hw_version(), spec.get_sw_version()))
	print('Sensor: %s, Pixel count: %d' % (spec.get_sensor_type(), spec.get_pixel_count()))
	print('Exposure time: %d ms, available range: %d : %d us' % (spec.get_exposure_time_ms(), spec.get_exposure_time_min_us(), spec.get_exposure_time_max_us()))
	print('Sensor t: %3.6f \'C, sink t: %3.6f\'C' %(spec.get_sensor_temp(), spec.get_sink_temp()))
	print('Averaging: %d, available range: %d : %d' % (spec.get_averaging(), spec.get_averaging_min(), spec.get_averaging_max()))
	print('Wavelength coefficients: ', (spec.get_wavelength_coefficients()))
	print('Nonlinearity coefficients: ', spec.get_nonlinearity_coefficients())
	print('Supply: %3.6f V, USB: %3.6f, cooling: %3.6f A' %(spec.get_supply_voltage(), spec.get_usb_voltage(), spec.get_cooling_current()))
	tec_status = spec.get_tec_status()
	print('TEC status: %s, target: %3.6f \'C ' % (tec_status.name, spec.get_target_temp()))
	spec.set_target_temp(-5.1)
	while tec_status != TECStatus.SETPOINT_REACHED:
		tec_status = spec.get_tec_status()
		print('Sensor t: %3.6f \'C, sink t: %3.6f\'C' % (spec.get_sensor_temp(), spec.get_sink_temp()))
		print('TEC status: %s' % spec.get_tec_status().name)
		time.sleep(3)
	exposure_time = 5000
	print('Setting exposure to %d ms' % exposure_time)
	spec.set_exposure_time_ms(exposure_time)
	print('New exposure time: %d ms' % (spec.get_exposure_time_ms()))
	print('Available spectra before capture: %d' % spec.get_available_spectra_count())
	spec.start_exposure()
	time.sleep(5)
	print('Available spectra after capture: %d' % spec.get_available_spectra_count())
	spectrum = spec.get_spectrum()
	print('Available spectra after getting one: %d' % spec.get_available_spectra_count())
	pprint(vars(spectrum.header))

	import matplotlib.pyplot as plt
	plt.clf()
	plt.plot(spec.get_wavelength_mapping(), spectrum.amplitudes)
	plt.title('Spectrum')
	plt.xlabel('Wavelength (nm)')
	plt.ylabel('ADC values')
	plt.draw()
	plt.show()
	plt.close()

	spec.terminate()
	sys.exit(0)