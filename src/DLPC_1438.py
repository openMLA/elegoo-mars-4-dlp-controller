import warnings
import RPi.GPIO as GPIO
import time
import enum
import math
import numpy as np

from img_convert import image_to_arr

# Pin numbering
PROJ_ON = 5
SYS_RDY = 6
HOST_IRQ = 19
SPI_RDY = 7
PRINT_ACTIVE = 13

SPI_BUFFERSIZE = 65536  # note the default config for raspberry pi is 4096

#  DLPC1438 on Anyubic board address
DLPC1438_addr = 0x1B

class Mode(enum.IntEnum):
    STANDBY = 0xFF,
    EXTERNALPRINT = 0x06,
    TESTPATTERN = 0x01

## TODO: consider making this object oriented with DLCP1438 class

def intialise_DLPC1438(i2c_bus):
    """
    Checks if the DCLP1438 is running and ready for i2c communication, and if not, will 
    start the DLPC1438 with the PROJ_ON gpio signal.
    """
    print("Intialising the DLPC1438...")

    # Configure the pins
    GPIO.setup(PROJ_ON, GPIO.OUT)  
    GPIO.setup(SYS_RDY, GPIO.IN)  
    GPIO.setup(HOST_IRQ, GPIO.IN)  
    GPIO.setup(SPI_RDY, GPIO.IN)  
    GPIO.setup(PRINT_ACTIVE, GPIO.IN)  


    ## TODO: avoid this line below, which forces a full restart of the DLPC1438
    # I think it interferes with how the Anhua board is designed...
    GPIO.output(PROJ_ON, GPIO.LOW)    
    time.sleep(1)
        
    # there are 2 options (see figure 9.1 of DLPC1438 datasheet):
    # [1] host_IRQ is low, and the DLPC1438 has not started yet
    # [2] host IRQ is low, but the DLCP1438 is already active and running

    try:  # we try to communicate over I2C. This will trow I/O error if DLPC1438 is not active yet
        i2c_bus.read_byte(DLPC1438_addr)  # check if i2c is already active. Then we are in [2]
        warnings.warn("DLPC1438 is already powered on when script initialised. No startup action needed.")
        return
    except IOError:  # DCLP1438 seems to still be turned off (case [1]). Let's start it
        print("Setting PROJ_ON high to start DLPC1438 startup sequence... ")

        # send the PROJ_ON signal and wait for the HOST_IRQ signal to go high, signalling the DLPC1438
        # is ready to go
        GPIO.output(PROJ_ON, GPIO.HIGH)
        ref_time = time.time()
        while not GPIO.input(HOST_IRQ):
            time.sleep(0.01)

        print(f"DLPC1438 is signalling it is ready for use, {time.time()-ref_time} seconds after PROJ_ON went high.")

        # now we need to wait for I2C communication to be ready
        time.sleep(1)  # TODO: make this more robust

        # keep looping as long as we cannot find the DLPC1438 on the i2c bus
        while i2c_bus.read_byte(DLPC1438_addr) == 0:  
            time.sleep(1)

        return


def switch_mode(new_mode, i2c_bus):
    """
    Switch between DLPC1438 operational modes.

    Note that the input of the function must be an Enum of the Mode class.
    """
    # check that the new mode is actually a valid enum entry 
    if isinstance(new_mode, Mode):  
        print(f"> Switching DLPC1438 mode to {new_mode.name}\t (currently in {i2c_bus.read_i2c_block_data(DLPC1438_addr,0x06,1)[0]})")

        i2c_bus.write_i2c_block_data(DLPC1438_addr, 0x05, [new_mode])  # send the new mode setting

        time.sleep(0.4)  # need some time to switch between modes

        # check that the mode switch was successful
        assert i2c_bus.read_i2c_block_data(DLPC1438_addr,0x06,1)[0] == new_mode.value, f"Was unable to switch the DLPC 1438 to MODE:{new_mode}"

    else:
        raise Exception("Invalid DLPC1438 mode provided. Use the Enum 'Mode', rather than the hex value.")
    

def configure_external_print(LED_PWM, i2c_bus, skip_FPGA_video=False):
    """
    Apply various settings applicable to the EXTERNAL_PRINT mode of the DLPC1438.

    This function will configure multiple registers. Note that switching to STANDBY mode will
    likely reset some of these values, so it is suggested to call this just before switching
    to EXTERNAL_PRINT mode.
    """
    print("\nConfiguring the DLPC1438 for external print mode...")

    # Write FPGA control (0xCA)
    # no CRC error injection, no CRC error calc, no FGPA reset, no FPGA reset unlock
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xCA, [0b00000000])  
    print(f"FPGA settings: {bin(i2c_bus.read_i2c_block_data(DLPC1438_addr,0xCB,1)[0])}")
    
    # write external print confugration (0xA8)
    # we choose a linear transfer function (byte 1) and select led 1 (byte 2)
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xA8, [0x00, 0b00000001])  
    print(f"External print settings: {i2c_bus.read_i2c_block_data(DLPC1438_addr,0xA9,2)}")

     # Write LED PWM current (0x54)
    # Set PWM value for LED 3/1
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0x54, [0xBE, 0x01, 0x00, 0x00, 0xBE, 0x01])  # TODO: figure out if we are dealing with LED1 or LED3, set other to 0
    print(f"LED settings: {[hex(val) for val in i2c_bus.read_i2c_block_data(DLPC1438_addr,0x55,6)]}")  # TODO: figure out why set values do not match setpoint

    # Write parallel video (0xC3)
    # Enable the FPGA parallel video interface.
    if not skip_FPGA_video:
        i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC3, [0x01])  
        print(f"prallel video settings: {bin(i2c_bus.read_i2c_block_data(DLPC1438_addr,0xC4,1)[0])}")

    # Write actuator orientation (0xC8)  # TODO: figure out if this one is really needed
    # see DLPC1438 programming guide for interpetation of these bytes. For now just using values of Elegoo board.
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC8, [0x03, 0x16, 0x11, 0x06, 0x01])  
    print(f"Actuator orientation settings: {[hex(val) for val in i2c_bus.read_i2c_block_data(DLPC1438_addr,0xC9,5)]}")


def  await_SYS_RDY():
    while not GPIO.input(SYS_RDY):
        time.sleep(0.3)
        print("waiting for SYS_RDY")


def expose_pattern(exposure_time,i2c_bus):
    assert GPIO.input(SYS_RDY), "SYS_RDY signal is not high yet, cannot expose frames yet."

    # Write External Print Control (C1)
    # start exposure of current buffer for infinite duration with 5 dark frames to let video data stabilise)
    print("> Starting UV exposure!")
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC1, [0x00, 0x05, 0x00, 0xFF, 0xFF])  
    # the value above never seem to be read back correctly if you read over I2C. Also on anyubic board.'

    time.sleep(0.1)
    if not GPIO.input(PRINT_ACTIVE): warnings.warn("PRINT ACTIVE did not go high after starting exposure. Something might be wrong.") 

    

def format_spi_data(col_start, col_end, row_start, pixel_data):
    length = pixel_data.size
    print(f"number of bytes to include in SPI: {length}")
    width = (col_end-col_start+1)*128

    assert length % width == 0, "Number of pixels in data does not describe a rectangle defined by column and row index"
    assert 0 <= col_start < 20, "col_start must be [0, 19]"
    assert 1 <= col_end < 20, "col_start must be [1, 19]"
    assert col_start < col_end, "col_start must be smaller than col_end"
    assert 0 <= row_start < 720, "row_start must be [0, 719]"

    height = int(length/width)

    print(f"Generating SPI data for image subframe of {width}x{height} pixels, starting at ({col_start*128},{row_start*2})")     

    rowcol_data_block_raw = col_start + (col_end << 5) + (row_start << 10) + (0b1111 << 28)
    rowcol_data_block = list(rowcol_data_block_raw.to_bytes(4, byteorder = 'little'))
    
    # this is not exactly optimised for performance  -> see if we can use numpy with spidev 
    preamble = [0x04] + rowcol_data_block + [0x00] + list(length.to_bytes(4, byteorder = 'little'))  # TODO: REMOVE
    data = preamble + pixel_data.tolist() + [0x00, 0x00] # TODO: do we need CRC bytes if we disabled the check?
    with open("spi.txt", "w") as output:
        output.write(str([bin(val) + " , " for val in preamble]))
    return data

def rowcol_data_block(col_start, col_end, row_start):
    rowcol_data_block_raw = col_start + (col_end << 5) + (row_start << 10) + (0b1111 << 28)
    rowcol_data_block = list(rowcol_data_block_raw.to_bytes(4, byteorder = 'little'))
    return  rowcol_data_block

def send_image_over_spi(offset_width, offset_height, pixel_data, spi_bus):
    """
    Generate (multiple) spi transfers to transfer image data to FPGA.

    Offset width specifies the offset of the image along width in pixels from (top) left of frame.
    Offset height is the same, but for the vertical offset in pixels from top (left) of frame.
    """

    img_width = pixel_data.shape[0]
    img_height = pixel_data.shape[1]
    
    assert img_width <= 2560, "Max image width is 2560 pixels"
    assert img_height <= 1440, "Max image height is 1440 pixels"

    # The SPI data format requires "start/end col" and "start_row"
    col_start = math.floor(offset_width/128)  # per 128
    row_start = math.floor(offset_height/2)  # per 2

    # if the offset is not a perfect multiple of 128 or 2, we will 0 pad the "start/front" pixel data
    pad_width_start = offset_width % 128
    pad_height_start = offset_height % 2

    # we also need to pad the "end/back" of the data because we can only specify end_col in steps
    # of 128.
    pad_width_end =  (128 - pad_width_start + img_width) % 128
    pad_height_end = (2 - pad_height_start + img_height) % 2

    print(f"Start col: {col_start} (leftpad:{pad_width_start}, rightpad:{pad_width_end})")
    print(f"Start row: {row_start} (leftpad:{pad_height_start}, rightpad:{pad_height_end})")

    # 0-pad the data 
    padded_data = np.pad(pixel_data, ((pad_width_start,pad_width_end), (pad_height_start,pad_height_end)))

    print(f"Original dims {pixel_data.shape}, padded dims: {padded_data.shape}")

    width = padded_data.shape[0]
    height = padded_data.shape[1]

    assert width % 128 == 0, "Padded data does not fit neatly in SPI transmission"
    assert height % 2 == 0, "Padded data does not fit neatly in SPI transmission"
    # we also need to check if the padded image is still within bounds as someone could input
    # a 2560x1440 image and shift it by e.g. 500,500 pixels, which obviously would not work 
    assert width <= 2560, "Image width after shifting exceeds the max width of 2560 pixels"
    assert height <= 1440, "Image height after shifting exceeds the max width of 1440 pixels"

    col_end = int(col_start + width/128 - 1)  # note: the width is start_col up to *and including* end_col

    print(f"End col: {col_end}")

    # now we need to figure out how many rows of data we can transfer in a single SPI transfer
    # based on the image width and our SPI buffer size. We need 10 bytes (or less) for other parts 
    # of SPI command besides pixel data.

    # TODO: ensure that this is always an even number!
    num_rows = math.floor( (SPI_BUFFERSIZE-10) / width) - 1  # TODO: can we be more efficient here?

    assert num_rows*width < (SPI_BUFFERSIZE - 10)  

    num_transfers = math.ceil(height / num_rows)
    print(f"The source image of dims {padded_data.shape} will be split into {num_transfers} transfers of (max) size {width}x{num_rows}")

    #  split the data into chunks. Note that the last chunk is probably smaller than the other ones
    split_data = np.split(padded_data, [(i+1)*num_rows for i in range(num_transfers-1)], axis=1)

    row_tracker = 0

    # Send the data over SPI in multiple tranmissions
    SPI_start = time.time()
    for (transfer_idx, data) in enumerate(split_data):
        print(f"- transfer {transfer_idx} has shape: {data.shape}")
        if transfer_idx == 0:
            preamble = [0x04] + rowcol_data_block(col_start, col_end, row_start) + [0x00] + list(padded_data.size.to_bytes(4, byteorder = 'little'))

        else:
            # note that following trasnfers do not contain the "length" of the transfer in preambe
            preamble = [0x04] + rowcol_data_block(col_start, col_end, row_start + row_tracker) + [0x00]
            
        print(f"row index {row_start + row_tracker}")  #TODO: remove
        row_tracker += int(data.shape[1] / 2)  # divided by 2 because the row_start is in steps of 2 (see SPI format)


        # Note that xfer3 has a max number of bytes it can transfer set in /sys/module/spidev/parameters/bufsiz
        spi_bus.writebytes2(np.insert(data.flatten("F"), 0, preamble))  #  CRC does not seemt o be needed
    print(f"SPI transfer took, {time.time()-SPI_start} seconds. At {spi_bus.max_speed_hz}Hz clock.")

def send_image_to_buffer(spi_bus, i2c_bus):
    print("> Sending Image Data over SPI...")
    pxldata = image_to_arr('../media/openMLA_logo_256x144.png')

    # select buffer 0 to be active (i.e. receive SPI data)
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC5, [0x00])  
    time.sleep(0.3)

    if not GPIO.input(SPI_RDY): warnings.warn("FPGA not ready to receive SPI data")  # TODO: check if this pin ever goes high

    # Note that xfer3 has a max number of bytes it can transfer set in /sys/module/spidev/parameters/bufsiz
    spi_bus.xfer3(format_spi_data(3, 4, 400, pxldata))

    time.sleep(0.3)

    # and make buffer 1 the active and have buffer 0 (with our data) be accessible to DLPC1438
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC5, [0x01])  
    print(f"Active buffer index: {i2c_bus.read_i2c_block_data(DLPC1438_addr,0xC6,1)[0]}")


def set_background(intensity, spi_bus, i2c_bus):
    print("> Setting all pixels to intensity:{intensity} and turning projector on!")

    assert 0 <= intensity < 255, "Intensity must be [0,255]"

    pxldata = (np.ones((2560, 1440))*intensity).astype(int)

    # select buffer 0 to be active (i.e. receive SPI data)
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC5, [0x01])  
    time.sleep(0.3)

    send_image_over_spi(0, 0, pxldata, spi_bus)

    time.sleep(0.3)

    # and make buffer 1 the active and have buffer 0 (with our data) be accessible to DLPC1438
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC5, [0x00])  
    print(f"Active buffer index: {i2c_bus.read_i2c_block_data(DLPC1438_addr,0xC6,1)[0]}")

def send_split_image_to_buffer(spi_bus, i2c_bus):
    print("> Sending Image Data over SPI... (SPLIT TECHNIQUE)")
    pxldata = image_to_arr('../media/openMLA_logo_1024x577.png')

    # select buffer 0 to be active (i.e. receive SPI data)
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC5, [0x01])  
    time.sleep(0.3)

    send_image_over_spi(550, 650, pxldata, spi_bus)

    time.sleep(0.3)

    # and make buffer 1 the active and have buffer 0 (with our data) be accessible to DLPC1438
    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0xC5, [0x00])  
    print(f"Active buffer index: {i2c_bus.read_i2c_block_data(DLPC1438_addr,0xC6,1)[0]}")


def test_FPGA(i2c_bus):
    """
    Debugging functions for the FPGA. 
    
    NOT Compatible with command 0xC3. Run configure_external_print() with skip_FPGA_video if
    you want to run these commands and see the test pattern.
    """
    FPGA_version = i2c_bus.read_i2c_block_data(DLPC1438_addr,0x64,4)
    print(f"FPGA version: {[bin(val) for val in FPGA_version]}")

    FPGA_status = i2c_bus.read_i2c_block_data(DLPC1438_addr,0x6F,2)
    print(f"FPGA status: {[bin(val) for val in FPGA_status]}")

    

    print(f"prallel video settings: {bin(i2c_bus.read_i2c_block_data(DLPC1438_addr,0xC4,1)[0])}")


    i2c_bus.write_i2c_block_data(DLPC1438_addr, 0x67, [0b00000011, 0x0B]) 
    print(f"FPGA testpattern settings: {[hex(val) for val in i2c_bus.read_i2c_block_data(DLPC1438_addr,0x68,2)]}")

    if not GPIO.input(SPI_RDY): warnings.warn("FPGA not ready to receive SPI data")