import logging


class SpectrometerBase:
    wavelength_coefficients = {
        'A': 0,
        'B1': 0,
        'B2': 0,
        'B3': 0,
        'B4': 0
    }

    # if no linear calibration coefficients are available on the EEPROM
    # default to coefficient 1
    linear_calibration_coefficients = {
        'B1': 1.0,
        'B2': 0.0,
        'B3': 0.0,
        'B4': 0.0,
        'B5': 0.0,
        'B6': 0.0,
        'B7': 0.0
    }
    wavelength_list = []
    pixel_count = 0

    def __init__(self, ser_read, ser_write, name="SpectrometerBase") -> None:
        self._write_fn = ser_write
        self._read_fn = ser_read
        self._log = logging.getLogger(name)
        self.wavelength_list = []
        self.reset()
        self.pixelCount = self.get_pixel_count()

    def get_wavelength_coefficients(self):
        return self.wavelength_coefficients

    def get_pixel_to_wavelength_mapping(self):
        if len(self.wavelength_list):
            return self.wavelength_list
        if self.wavelength_coefficients['A'] == 0:
            self._fill_wavelength_coeffs()
        for p in range(self.pixel_count):
            self.wavelength_list.append(
                self.wavelength_coefficients['A'] +
                self.wavelength_coefficients['B1'] * p +
                self.wavelength_coefficients['B2'] * p**2 +
                self.wavelength_coefficients['B3'] * p**3 +
                self.wavelength_coefficients['B4'] * p**4
            )
        return self.wavelength_list

    def get_serial_number(self):
        raise NotImplementedError

    def get_pixel_count(self):
        raise NotImplementedError

    def get_integration_time(self):
        raise NotImplementedError

    def _fill_wavelength_coeffs(self):
        raise NotImplementedError

    def set_integration_time_ms(self, it):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError

    def get_spectrum(self, integration_time):
        raise NotImplementedError

    # compensate for linear offset
    def apply_linear_calibration(self, spectrum):
        s = []
        if len(self.linear_calibration_coefficients):
            for val in spectrum:
                s.append(
                    self.linear_calibration_coefficients['B1'] * val +
                    self.linear_calibration_coefficients['B2'] * val ** 2 +
                    self.linear_calibration_coefficients['B3'] * val ** 3 +
                    self.linear_calibration_coefficients['B4'] * val ** 4 +
                    self.linear_calibration_coefficients['B5'] * val ** 5 +
                    self.linear_calibration_coefficients['B6'] * val ** 6 +
                    self.linear_calibration_coefficients['B7'] * val ** 7
                )
        return s
