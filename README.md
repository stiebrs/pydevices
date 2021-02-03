# python-devices
DISCLAIMER:

Not for production use! These drivers are written by an amateur and might damage your instrument. Consider this a liability waiver.  

Python drivers for various devices. Implemented only as much as I have had a need for. Usage examples are under each device tests:
- Instrument: instrumentation
  - DMM: digital multimeters with remote operation capability
    - Keythley 2000 over GPIB, simple test 
  - spectrometer:
    - Broadcom
        - QRed SWIR with TEC. I didn't particularly like their Python driver implementation plus it had a few bits unimplemented (e.g. thermal control)
- interface: different interfacing devices
  - gpib:
    - Prologix USB-GPIB interface

Testing:
```sh
python -m instrument.dmm.keythley2000.test.test
```
