import RPi.GPIO as GPIO
import time
import smbus  # I2C
import spidev  # SPI
from DLPC_1438 import *


GPIO.setmode(GPIO.BCM)

try:
    # Initialize I2C (SMBus) on channel 1
    bus = smbus.SMBus(1)

    # Initialise SPI (bus 0, with CE0 as chip select pin)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 500000  # up to 50 MB/s
    spi.mode = 3  #TODO: figure out which mode is right. See https://e2e.ti.com/support/dlp-products-group/dlp/f/dlp-products-forum/1187357/dlp300s-dlp300s-and-dlpc1438-application-sample

    # Initialise the DLPC1438
    intialise_DLPC1438(bus)
   
    #  DLPC1438 on Anyubic board address
    DLPC1438_addr = 0x1B

    mode = bus.read_i2c_block_data(DLPC1438_addr,0x06,1)  # probably standby if just initialised
    print(f"we are in mode: {mode}")

    # # switch to testpattern mode
    # switch_mode(Mode.TESTPATTERN, bus)

    # # enable flood light
    # bus.write_i2c_block_data(DLPC1438_addr, 0x16, [0b00001111])
    # time.sleep(2)  # lit for 2s
    # bus.write_i2c_block_data(DLPC1438_addr, 0x16, [0b00000000])
    # time.sleep(1)  # back to testpattern (dim)i2c

    # # and back to standby
    # switch_mode(Mode.STANDBY, bus)

    # let's try external print mode now
    configure_external_print(0, bus)
    switch_mode(Mode.EXTERNALPRINT, bus)

    # it will take maybe a second for SYS_RDY to go high and we need to wait for that before exposing
    await_SYS_RDY()  
    configure_external_print(0, bus)


    send_image_to_buffer(spi, bus)  # send the image data into FPGA buffer over SPI
    time.sleep(0.5)
    expose_pattern(0, bus)


    time.sleep(3)  # wait before cleanup

    # and back to standby
    switch_mode(Mode.STANDBY, bus)
    GPIO.cleanup()

except KeyboardInterrupt:
    GPIO.cleanup()