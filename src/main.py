import RPi.GPIO as GPIO
import time
import numpy as np
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
    spi.max_speed_hz = 125000000  # FPGA/DCLP1438 limit: 50 MB/s; 125MHz seems limit for Pi zero 1W
    spi.mode = 3 

    # Initialise the DLPC1438
    DMD = DLPC1438(i2c, spi)
   
    # as an example, let's manually read some i2c information
    mode = i2c.read_i2c_block_data(DMD.addr,0x06,1)  # probably standby if just initialised
    print(f"we are in mode: {mode}")

    # let's try external print mode now
    DMD.configure_external_print(LED_PWM = 1000)
    DMD.switch_mode(Mode.EXTERNALPRINT)

    # intialise FPGA buffers to zero
    DMD.set_background(intensity = 0, both_buffers = True)

    # Send an image, where the raspberry pi determines the exposure time
    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 0,0)  # send the image data into FPGA buffer over SPI
    DMD.swap_buffer()
    DMD.expose_pattern(exposed_frames = -1)  # infinite exposure time, until we send the stop_exposure() command
    time.sleep(4)
    DMD.stop_exposure()  # and then manually stop exposure

    # Now let's send another image, but let the DLPC1438 handle the exp time (probably more precise)
    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 639,300)  # send the image data into FPGA buffer over SPI
    DMD.swap_buffer()
    DMD.expose_pattern(exposed_frames = 200)  #  expose for 200 frames (= 200/60 ~ 3.3s) 
    time.sleep(4)  # just to rule out buffer swap while it is exposing.
                   # if you want to explicitly wait for the exposure to finish, you can check for
                   # the pin PRINT_ACTIVE to go low.  

    DMD.set_background(0, both_buffers=True)  # let's clear the buffers again (set all pixels to 0)
    
    # Let's now send an image to buffer, and then send the next image into the buffer while the 
    # previous one is exposing
    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 1279,0)  # send the image data into FPGA buffer over SPI
    DMD.swap_buffer()
    DMD.expose_pattern(exposed_frames = -1)  # exposure until we send stop command 
    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 0,719)  # send the image data into FPGA buffer over SPI
    time.sleep(0.5)  # just for illustrative purposes
    DMD.stop_exposure()  # and then manually stop exposure, but the next buffer is already ready
    DMD.swap_buffer()  # swap 2nd image into active buffer
    DMD.expose_pattern(exposed_frames = -1)  # We expose the next image, that we sent to buffer while the last image was exposing
    time.sleep(4)  # show the 2nd images
    DMD.stop_exposure()  # and then manually stop exposure

    # If you only need two images, you can quickly swap between buffers (but with fast enough
    # SPI, you can probably send a completely new image into buffer in time for the next frame,
    # especially if you draw only to a small portion of the screen.)
    for i in range(15):
        DMD.swap_buffer()
        DMD.expose_pattern(exposed_frames = -1)  
        time.sleep(0.2)
        DMD.stop_exposure()  # and then manually stop exposure

    # Of course we can also send a dynamically generated numpy array
    # lets send a numpy array with elements "below the diagonal" all 255
    DMD.set_background(0, both_buffers=True)  # clearing previous images
    pixeldata = np.tri(500, dtype=np.uint8)*255
    DMD.send_pixeldata_to_buffer(pixeldata, 400,400)  # send array containging triangle
    DMD.swap_buffer()
    DMD.expose_pattern(exposed_frames = -1)   
    time.sleep(2)
    DMD.stop_exposure()  

    # You may also want to update an existing frame, rather than redrawing the entire
    # image in the other buffer. In that case, just swap the buffer twice
    DMD.set_background(0, both_buffers=True)  
    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 200,200)  # first version of image
    DMD.swap_buffer()
    DMD.expose_pattern(exposed_frames = -1)   
    time.sleep(2)
    DMD.stop_exposure()  
    DMD.swap_buffer()  # swap buffer again, so we have the first version of image in inactive buffer
    DMD.send_image_to_buffer('../media/openMLA_logo_1280x720.png', 400,400)  # draw on top of first image
    DMD.swap_buffer()  # make buffer active again
    DMD.expose_pattern(exposed_frames = -1)   
    time.sleep(2)
    DMD.stop_exposure() 


    # Let's display a full-frame image
    DMD.send_image_to_buffer('../media/openMLA_logo_2560x1440.png', 0,0)  # send the image data into FPGA buffer over SPI
    DMD.swap_buffer()
    DMD.expose_pattern(exposed_frames = -1)  #  expose for inifinite duration (until we manually stop it)
    time.sleep(3) 
    DMD.stop_exposure()  # and then manually stop exposure

    time.sleep(1) 

    # and back to standby
    DMD.switch_mode(Mode.STANDBY)
    GPIO.cleanup()

except KeyboardInterrupt:
    GPIO.cleanup()