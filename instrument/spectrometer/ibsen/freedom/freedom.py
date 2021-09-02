import logging
import math
from textwrap import wrap

SN_REG_ADDR = 1
HW_VER_REG_ADDR = 2
FW_VER_REG_ADDR = 3
DET_TYPE_REG_ADDR = 4
PIX_PER_IMG_REG_ADDR = 5
CAL_DATA_CHAR_COUNT_REG_ADDR = 6
CAL_DATA_REG_ADDR = 7
SENSOR_CTRL_REG_ADDR = 8
SENSOR_EXP_TIME_LSB_REG = 9
SENSOR_EXP_TIME_MSB_REG = 10
TEMP_REG_ADDR = 11
PIXELS_READY_REG_ADDR = 12
TRIGGER_DELAY_LSB = 13
TRIGGER_DELAY_MSB = 14
ADC_GAIN_REG_ADDR = 15
ADC_OFFSET_REG_ADDR = 16
PERM_STORAGE_REG_ADDR = 17
MPP_REG_ADDR = 18
DATA_READY_THLD_REG_ADDR = 19
ERROR_REG_ADDR = 62
PROD_MODE_REG_ADDR = 63


class Spectrometer:
	wlCalCoeffs = {}
	# if no linear calibration coefficients are available on the EEPROM
	# default to coefficient 1
	linCalCoeffs = {
		'A': 1.0,
		'B1': 0.0,
		'B2': 0.0,
		'B3': 0.0,
		'B4': 0.0,
		'B5': 0.0,
		'B6': 0.0,
		'B7': 0.0
	}
	waveLengthList = []
	pixelCount = 0

	exchangeCmdFn = None
	readDataFn = None
	gpioReadPinFn = None

	'''
	All the hardware interfaces have to be set up externally
	Constructor expects only data exchange functions passed in
	bytes exchangeCmdFn(bytes) should deal with chip-select (CS0) and SPI trasfers internally
		accept bytes object to send and return bytes object with response
	bytes readDataFn(count) should deal with chip-select (CS1) and SPI transfers internally
		count argument indicates expected number of 8bit bytes to receive in a response
	int gpioFn() should return DATA_READY pin status (1 for set, 0 reset).
		Usage of this function is implemented in polling mode
	Getting and releasing the interfaces has to be performed externally
	'''
	def __init__(self, exchangeCmdFn, readDataFn, gpioFn):
		self.log = logging.getLogger('Ibsen_Freedom')
		self.log.setLevel(logging.DEBUG)
		self.pixelCount = 0
		self.wlCalCoeffs = {}
		self.exchangeCmdFn = exchangeCmdFn
		self.readDataFn = readDataFn
		self.gpioReadPinFn = gpioFn
		# try reading some known fixed values as comms check
		if self.getPixelsPerImage() != 2048:
			raise Exception("Bad pixel count. Either comms error or wrong device!")
		self.getCalDataValues()

	def getGain(self):
		val = self.readReg(ADC_GAIN_REG_ADDR, 2)[1]
		gain = 6.0 / (1 + 5.0 * ((63 - val)/63))
		return gain

	def getSerialNo(self):
		val = self.readReg(SN_REG_ADDR, 2)
		return mergeBytes(val)

	def getHwVersion(self):
		val = self.readReg(HW_VER_REG_ADDR, 2)[0]
		return val

	def getFwVersion(self):
		val = self.readReg(FW_VER_REG_ADDR, 2)
		return mergeBytes(val)

	def getDetectorType(self):
		val = self.readReg(DET_TYPE_REG_ADDR, 2)
		return mergeBytes(val)

	def getSensorTemp(self):
		NTC_B = 3762.32
		NTC_R0 = 10.0
		NTC_R_PULLUP = 10.0
		NTC_T0 = float(25.0 + 273.15)
		val = self.readReg(TEMP_REG_ADDR, 2)
		adcVal = float(mergeBytes(val)) / 0xFFF
		resistance = NTC_R_PULLUP * adcVal / (1 - adcVal)
		rLog = math.log(resistance/NTC_R0)
		absTemp = 1 / ((1/NTC_T0) + (1/NTC_B) * rLog)
		celsTemp = absTemp - 273.15
		return celsTemp

	def getPixelsPerImage(self):
		if self.pixelCount > 0:
			return self.pixelCount
		val = self.readReg(PIX_PER_IMG_REG_ADDR, 2)
		self.pixelCount = mergeBytes(val)
		return self.pixelCount

	# Reading CALIB_DATA_CHARS reg resets the pointer to first
	# should return total number of calibration data characters 
	# for both wavelength (wl) and linearity calibration coefficients
	# if latter is available (paid option). By default should return 84
	def getNumberOfCalDataCharsAndResetPointer(self):
		val = self.readReg(CAL_DATA_CHAR_COUNT_REG_ADDR, 2)
		return mergeBytes(val)

	'''
	CALIB_DATA contains series of ASCII characters
	in form of "+2.1234567E+05". These have to be read char-by-char
	and used for linearity correction
	'''
	def getCalDataValues(self):
		# reading CALIB_DATA_CHARS resets internal memory pointer
		charCount = self.getNumberOfCalDataCharsAndResetPointer()
		if charCount <= 6*14:
			self.log.warning('No linearity calibration coefficients available')
		dataBytes = bytearray()
		# have to read bytes in separate transactions
		# because chip does not increment pointer until CS is released
		while charCount != 0:
			dataBytes.append(self.readReg(CAL_DATA_REG_ADDR, 2)[1])
			charCount = charCount - 1
		string = dataBytes.decode(encoding='ASCII')
		coeffStrings = wrap(string, 14)

		for idx, c in enumerate(coeffStrings):
			if idx < 6:
				self.wlCalCoeffs['B' + str(idx)] = float(c)
			elif idx == 6:
				self.linCalCoeffs['A'] = float(c)
			else:
				self.linCalCoeffs['B' + str(idx-6)] = float(c)

		# assemble the list of pixel to wl mappings
		for i in range(self.pixelCount):
			self.waveLengthList.append(self.wlCalCoeffs['B0'] +
									self.wlCalCoeffs['B1'] * i +
									self.wlCalCoeffs['B2'] * i +
									self.wlCalCoeffs['B3'] * i +
									self.wlCalCoeffs['B4'] * i +
									self.wlCalCoeffs['B5'] * i)

	def getExposureTimeInNs(self):
		lsb = mergeBytes(self.readReg(SENSOR_EXP_TIME_LSB_REG, 2))
		msb = mergeBytes(self.readReg(SENSOR_EXP_TIME_MSB_REG, 2))
		# for whatever reason, 48 counts (9600ns) are always added 
		return ((msb << 16 | lsb) + 48) * 200

	def setExposureTimeInMs(self, val):
		self.setExposureTimeInNs(val*1000*1000)

	def getExposureTimeInMs(self):
		return self.getExposureTimeInNs() / 1000 / 1000

	def setExposureTimeInNs(self, val):
		correctedVal = int(round((float(val) - 48.0*200.0) / 200.0))
		# just in case take only lower bits
		msb = ((correctedVal & 0xFFFFFFFF) >> 16) & 0xFFFF
		lsb = (correctedVal & 0xFFFF)
		self.writeReg(SENSOR_EXP_TIME_LSB_REG, bytearray([(lsb >> 8) & 0xFF, (lsb & 0xFF)]))
		self.writeReg(SENSOR_EXP_TIME_MSB_REG, bytearray([(msb >> 8) & 0xFF, (msb & 0xFF)]))

	def getTriggerDelayInNs(self):
		lsb = mergeBytes(self.readReg(TRIGGER_DELAY_LSB, 2))
		msb = mergeBytes(self.readReg(TRIGGER_DELAY_MSB, 2))
		return (msb << 16 | lsb) * 200

	def setTriggerDelayInNs(self, val):
		correctedVal = int(round(val / 200))
		msb = ((correctedVal & 0xFFFFFFFF) >> 16) & 0xFFFF
		lsb = (correctedVal & 0xFFFF)
		self.writeReg(TRIGGER_DELAY_LSB, bytearray([(lsb >> 8), (lsb & 0xFF)]))
		self.writeReg(TRIGGER_DELAY_MSB, bytearray([(msb >> 8), (msb & 0xFF)]))

	def getPixelsReadyCount(self):
		return mergeBytes(self.readReg(PIXELS_READY_REG_ADDR, 2))

	# number of pixels that have to be stored on FPGA before it triggers DR pin
	def getDataReadyThreshold(self):
		return mergeBytes(self.readReg(DATA_READY_THLD_REG_ADDR, 2))

	def setDataReadyThreshold(self, pixelCount):
		# register is 12 bits wide
		self.writeReg(DATA_READY_THLD_REG_ADDR, bytearray([((pixelCount >> 8) & 0x0F), (pixelCount & 0xFF)]))

	def getADCOffsetInMv(self):
		adcVal = mergeBytes(self.readReg(ADC_OFFSET_REG_ADDR, 2))
		sign = 1 if (adcVal & (1 << 8)) else -1
		return sign * (300 * ((adcVal & 0xFF)/255))

	def setADCOffsetInMv(self, val):
		sign = 1 if (val >= 0) else 0
		adcVal = (round(val/300 * 255)) & 0xFF
		self.writeReg(ADC_OFFSET_REG_ADDR, bytearray([sign, (adcVal & 0xFF)]))

	def softResetBuf(self):
		self.writeReg(SENSOR_CTRL_REG_ADDR, bytearray([(1 << 4)]))

	def triggerExposure(self):
		# just in case, clear buffer of existing data
		# this should not be done if continuous measurement is preferred
		self.softResetBuf()
		self.writeReg(SENSOR_CTRL_REG_ADDR, bytearray([1]))

	'''
	Read out the data from the FPGA buffer word by word
	Returns an array of pixel-indexed data
	Use pixel-indexed wavelength data from getPixelToWlMappings() 
	to obtain array of wavelengths for each pixel
	'''
	def get_spectrum(self, use_correction=True):
		spectrum = []

		# in continuous read spidev driver reads in some garbage and after reading all pixels
		# spectrometer signals that there's more data available,
		# so we have to wait for each byte read into FPGA image buffer
		# signalled by pulling the DATA_READY pin up
		while len(spectrum) < self.pixelCount:
			# if self.gpioReadPinFn() == 1:
			data = self.readDataFn(2)
			val = mergeBytes(data)

			if use_correction:
				# calculate correction factor, should be 1 or less
				C = (self.linCalCoeffs['A'] +
					self.linCalCoeffs['B1'] * val +
					self.linCalCoeffs['B2'] * val +
					self.linCalCoeffs['B3'] * val +
					self.linCalCoeffs['B4'] * val +
					self.linCalCoeffs['B5'] * val +
					self.linCalCoeffs['B6'] * val +
					self.linCalCoeffs['B7'] * val)
				# apply correction factor
				correctedVal = val / C
				spectrum.append(correctedVal)
			else:
				spectrum.append(val)
		return spectrum

	def get_pixel_to_wl_mapping(self):
		return self.waveLengthList

	def printInfo(self):
		serNo = self.getSerialNo()
		if serNo == 0:
			self.log.error('Communications error with spectrometer (serial number returned 0)')
			return

		print('Serial No: {}'.format(serNo))
		print('HW version: {}'.format(self.getHwVersion()))
		print('FW version: {}'.format(self.getFwVersion()))
		print('Gain setting: {:3.6f}'.format(self.getGain()))
		print('Offset: {:3.6f} mV'.format(self.getADCOffsetInMv()))
		print('Detector type: {}'.format(self.getDetectorType()))
		print('Pixels per image: {}'.format(self.pixelCount))
		print('Calibration character count: {}'.format(self.getNumberOfCalDataCharsAndResetPointer()))
		print('Exposure time: {} ns'.format(self.getExposureTimeInNs()))
		print('Trigger delay: {} ns'.format(self.getTriggerDelayInNs()))
		print('Data ready triggering threshold: {}'.format(self.getDataReadyThreshold()))

	'''
	Read register from the spectrometer
	reg - register code (use constants in header)
	len - expected response length in bytes
	'''
	def readReg(self, reg, count):
		self.log.debug("Reading reg {}, count {}".format(reg, count))
		regNew = ((reg << 2) | 2)
		val = self.transfer(bytes([regNew]), count)
		return val

	# Expect bytes of data to send
	def writeReg(self, reg, values):
		self.log.debug("Writing reg {} values {}".format(reg, values))
		regNew = (reg << 2)
		values.insert(0, regNew)
		self.transfer(bytes(values))

	def transfer(self, cmd, readLength=0):
		self.log.debug('> ' + ' '.join('{:02x}'.format(c) for c in cmd))
		val = self.exchangeCmdFn(cmd, readLength)
		self.log.debug('< ' + ' '.join('{:02x}'.format(c) for c in val))
		return val

def mergeBytes(arr):
	return arr[0] << 8 | arr[1]

