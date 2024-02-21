import RPi.GPIO as GPIO
import time
import smbus  # i2c
from DLPC_1438 import intialise_DLPC1438, switch_mode, Mode


GPIO.setmode(GPIO.BCM)

try:
    # Initialize I2C (SMBus) on channel 1
    bus = smbus.SMBus(1)

    # Initialise the DLPC1438
    intialise_DLPC1438(bus)
   
    #  DLPC1438 on Anyubic board address
    DLPC1438_addr = 0x1B

    mode = bus.read_i2c_block_data(DLPC1438_addr,0x06,1)  # probably standby if just initialised
    print(f"we are in mode: {mode}")

    # switch to testpattern mode
    switch_mode(Mode.TESTPATTERN, bus)

    # enable flood light
    bus.write_i2c_block_data(DLPC1438_addr, 0x16, [0b00001111])
    time.sleep(3)  # lit for 3s
    bus.write_i2c_block_data(DLPC1438_addr, 0x16, [0b00000000])
    time.sleep(1)  # back to testpattern (dim)

    # and back to standby
    switch_mode(Mode.STANDBY, bus)

    GPIO.cleanup()

except KeyboardInterrupt:
    GPIO.cleanup()