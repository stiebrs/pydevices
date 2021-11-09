import logging

from serial import Serial, time


import matplotlib.pyplot as plt

from vm_proto_gui.pydevices.instrument.spectrometer.ibsen.rock.rock import Spectrometer, OutputFormat, CaptureType

logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
	s = None
	try:
		s = Serial('/dev/ttyUSB1', baudrate=921000)
		s.timeout = 0.3
		spec = Spectrometer(s.read, s.write)
		print("Device ID: {}, version: {}, SN: {}".format(spec.get_id(), spec.get_version(), spec.get_serial_number()))
		print('Pixel count: {}'.format(spec.get_pixel_count()))
		print('Current baud rate: {}'.format(spec.get_baud_rate()))
		print('Default IT: {}'.format(spec.get_integration_time()))
		spec.set_integration_time_ms(500)
		print('New IT: {}'.format(spec.get_integration_time()))
		print('WL calibration coeffs: {}:'.format(spec.get_wavelength_coefficients()))
		print('Pixel to WL mappings:')
		p2wl = spec.get_pixel_to_wavelength_mapping()
		for p in range(spec.pixel_count):
			print('Pixel number: \t{}, \tWL: \t{} nm'.format(p, p2wl[p]))

		# need to capture dark manually beforehand, otherwise spectrometer returns zeroes
		# input("Cover the input and press ENTER to take dark")
		# dark = spec.capture(CaptureType.DARK, 100, 1, OutputFormat.ASCII_W_SPACES)
		# input('Remove cover to take exposed')
		spectrum = spec.capture(CaptureType.LIGHT, 100, 1, OutputFormat.ASCII_W_SPACES)
		# spectrum = spec.fetch_last(CaptureType.LIGHT,OutputFormat.ASCII_W_SPACES)
		# dark = spec.fetch_last(CaptureType.DARK, OutputFormat.ASCII_W_SPACES)
		# subtracted = spec.fetch_last(CaptureType.SUBTRACTED, OutputFormat.ASCII_W_SPACES)

		fig, ax = plt.subplots()
		ax.plot(p2wl, spectrum, 'b-')
		# ax.plot(p2wl, dark, 'r-')
		# ax.plot(p2wl, subtracted, 'r-')
		# plt.show()
		print(spectrum)
	finally:
		s.close()

