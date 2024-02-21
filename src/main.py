import RPi.GPIO as GPIO
import time
import smbus  # i2c
from DLPC_1438 import intialise_DLPC1438


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
    bus.write_i2c_block_data(DLPC1438_addr, 0x05, [0x01])  # testpattern (seems quite dim in default state)
    mode = bus.read_i2c_block_data(DLPC1438_addr,0x06,1) 
    print(f"are we in tespattern mode? : {mode}")

    # enable flood light
    bus.write_i2c_block_data(DLPC1438_addr, 0x16, [0b00001111])
    time.sleep(3)  # lit for 3s
    bus.write_i2c_block_data(DLPC1438_addr, 0x16, [0b00000000])
    time.sleep(1)  # back to testpattern (dim)

    # and back to standby
    bus.write_i2c_block_data(DLPC1438_addr, 0x05, [0xFF])  # standby
    mode = bus.read_i2c_block_data(DLPC1438_addr,0x06,1) 
    print(f"back in standby? : {mode}")

    GPIO.cleanup()

except KeyboardInterrupt:
    GPIO.cleanup()