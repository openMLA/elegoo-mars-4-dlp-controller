import RPi.GPIO as GPIO
import time
import smbus  # I2C
import spidev  # SPI
from UV_projector.controller import DLPC1438, Mode


GPIO.setmode(GPIO.BCM)

try:
    # Initialize I2C (SMBus) on channel 1
    i2c = smbus.SMBus(1)

    # Initialise SPI (bus 0, with CE0 as chip select pin)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 30000000  # up to 50 MB/s
    spi.mode = 3  #TODO: figure out which mode is right. See https://e2e.ti.com/support/dlp-products-group/dlp/f/dlp-products-forum/1187357/dlp300s-dlp300s-and-dlpc1438-application-sample

    # Initialise the DLPC1438
    DMD = DLPC1438(i2c, spi)
   
    # as an example, let's manually read some i2c information
    mode = i2c.read_i2c_block_data(DMD.addr,0x06,1)  # probably standby if just initialised
    print(f"we are in mode: {mode}")

    # let's try external print mode now
    DMD.configure_external_print(LED_PWM = 512)
    DMD.switch_mode(Mode.EXTERNALPRINT)

    DMD.set_background(0)  # set every pixel to 0 (as a demo) - takes about 6s to transfer data

    time.sleep(1)

    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 640,360)  # send the image data into FPGA buffer over SPI
    DMD.expose_pattern(exposed_frames = 200)  #  expose for 200 frames (= 200/60 ~ 3.3s) 

    time.sleep(5)  # the pattern should stop before this timer runs out

    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 0,0)  # send the image data into FPGA buffer over SPI
    DMD.expose_pattern(exposed_frames = -1)  #  expose for inifinite duration (until we manually stop it)

    time.sleep(1)  # wait one second

    DMD.stop_exposure()  # and then manually stop exposure

    time.sleep(1) 

    # and back to standby
    DMD.switch_mode(Mode.STANDBY)
    GPIO.cleanup()

except KeyboardInterrupt:
    GPIO.cleanup()