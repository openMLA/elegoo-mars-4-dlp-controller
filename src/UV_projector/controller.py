import warnings
import RPi.GPIO as GPIO
import time
import enum
import math
import numpy as np

from UV_projector.img_convert import image_to_arr

class Mode(enum.IntEnum):
    STANDBY = 0xFF,
    EXTERNALPRINT = 0x06,
    TESTPATTERN = 0x01
    
class DLPC1438:
    """
    Representation of the DLPC1438 DMD controller. Communication between the user board (raspberry
    pi) and the DLPC1438+FPGA are handled through this class.
    """

    # Pin numbering
    PROJ_ON = 5
    SYS_RDY = 6
    HOST_IRQ = 19
    SPI_RDY = 7
    PRINT_ACTIVE = 13

    SPI_BUFFERSIZE = 65536  # note the default config for raspberry pi is 4096
    SPI_BUFFER_INDEX = 0  # FPGA buffer index that user can write to. Swapped after each image change

    addr = 0x1B  # i2c address

    def __init__(self, i2c_bus, spi_bus):
        """
        Checks if the DCLP1438 is running and ready for i2c communication, and if not, will 
        start the DLPC1438 with the PROJ_ON gpio signal.
        """
        print("Intialising the DLPC1438...")

        # Configure the pins
        GPIO.setup(self.PROJ_ON, GPIO.OUT)  
        GPIO.setup(self.SYS_RDY, GPIO.IN)  
        GPIO.setup(self.HOST_IRQ, GPIO.IN)  
        GPIO.setup(self.SPI_RDY, GPIO.IN)  
        GPIO.setup(self.PRINT_ACTIVE, GPIO.IN)  

        self.i2c = i2c_bus
        self.spi = spi_bus


        ## TODO: avoid this line below, which forces a full restart of the DLPC1438
        # I think it interferes with how the Anhua board is designed...
        GPIO.output(self.PROJ_ON, GPIO.LOW)    
        time.sleep(1)
            
        # there are 2 options (see figure 9.1 of DLPC1438 datasheet):
        # [1] host_IRQ is low, and the DLPC1438 has not started yet
        # [2] host IRQ is low, but the DLCP1438 is already active and running

        try:  # we try to communicate over I2C. This will trow I/O error if DLPC1438 is not active yet
            i2c_bus.read_byte(self.addr)  # check if i2c is already active. Then we are in [2]
            warnings.warn("DLPC1438 is already powered on when script initialised. No startup action needed.")

            # check the current active buffer
            self.SPI_BUFFER_INDEX = self.__i2c_read(0xC6,1)[0]
            print(f"Active buffer index at startup: {self.SPI_BUFFER_INDEX}")

            return
        except IOError:  # DCLP1438 seems to still be turned off (case [1]). Let's start it
            print("Setting PROJ_ON high to start DLPC1438 startup sequence... ")

            # send the PROJ_ON signal and wait for the HOST_IRQ signal to go high, signalling the DLPC1438
            # is ready to go
            GPIO.output(self.PROJ_ON, GPIO.HIGH)
            ref_time = time.time()
            while not GPIO.input(self.HOST_IRQ):
                time.sleep(0.01)

            print(f"DLPC1438 is signalling it is ready for use, {time.time()-ref_time} seconds after PROJ_ON went high.")

            # now we need to wait for I2C communication to be ready
            time.sleep(1)  # TODO: make this more robust

            # keep looping as long as we cannot find the DLPC1438 on the i2c bus
            while i2c_bus.read_byte(self.addr) == 0:  
                time.sleep(1)

            # check the current active buffer
            self.SPI_BUFFER_INDEX = self.__i2c_read(0xC6,1)[0]
            print(f"Active buffer index at startup: {self.SPI_BUFFER_INDEX}")

            return
        
    def __i2c_read(self, register, length):
        """Read I2C information from DCLP1438 at given register, expecting a certain number of bytes
        of data.
        
        This function exists primarily to keep a code more readable."""
        return self.i2c.read_i2c_block_data(self.addr,register,length)
    
    def __i2c_write(self, register, data):
        """Write I2C information from DCLP1438 at given register, sending a list of bytes specified
        in 'data'.
        
        This function exists primarily to keep a code more readable."""
        return self.i2c.write_i2c_block_data(self.addr,register,data)

    def switch_mode(self, new_mode):
        """
        Switch between DLPC1438 operational modes.

        Note that the input of the function must be an Enum of the Mode class.
        """
        # check that the new mode is actually a valid enum entry 
        if isinstance(new_mode, Mode):  
            print(f"> Switching DLPC1438 mode to {new_mode.name}\t (currently in {self.__i2c_read(0x06,1)[0]})")

            self.__i2c_write(0x05, [new_mode])  # send the new mode setting

            time.sleep(0.4)  # need some time to switch between modes

            # check that the mode switch was successful
            queried_mode = self.__i2c_read(0x06,1)[0]
            assert queried_mode == new_mode.value, f"Was unable to switch the DLPC 1438 to MODE:{new_mode}"

            # if we switched to EXTERNAL_PRINT mode, we will want to wait for 
            # SYS_READY to go high before doing anything else.
            if queried_mode == Mode.EXTERNALPRINT:
                self.__await_SYS_RDY()

        else:
            raise Exception("Invalid DLPC1438 mode provided. Use the Enum 'Mode', rather than the hex value.")
    
    def configure_external_print(self, LED_PWM, skip_FPGA_video=False): 
        """
        Apply various settings applicable to the EXTERNAL_PRINT mode of the DLPC1438.

        This function will configure multiple registers. Note that switching to STANDBY mode will
        likely reset some of these values, so it is suggested to call this just before switching
        to EXTERNAL_PRINT mode.
        """

        print(f"\nConfiguring the DLPC1438 for external print mode with LED PWM at {LED_PWM/1023*100}%")

        assert isinstance(LED_PWM, int), "LED_PWM must be a 10-bit integer"
        assert 0 <= LED_PWM < 1024, "LED_PWM must be 10-bit (i.e. in range [0, 1023])"

        # Write FPGA control (0xCA)
        # no CRC error injection, no CRC error calc, no FGPA reset, no FPGA reset unlock
        self.__i2c_write(0xCA, [0b00000000])  
        print(f"FPGA settings: {bin(self.__i2c_read(0xCB,1)[0])}")
        
        # write external print confugration (0xA8)
        # we choose a linear transfer function (byte 1) and select led 1 (byte 2)
        self.__i2c_write(0xA8, [0x00, 0b00000001])  
        print(f"External print settings: {self.__i2c_read(0xA9,2)}")

        # Write LED PWM current (0x54)
        # Set PWM value for LED 3/1
        print(LED_PWM.to_bytes(2, byteorder = 'big'))
        PWM_data = list(LED_PWM.to_bytes(2, byteorder = 'little')) + [0x00, 0x00, 0x00, 0x00]
        self.__i2c_write(0x54, PWM_data)  
        print(f"LED settings: {[hex(val) for val in self.__i2c_read(0x55,6)]}") 

        # Write parallel video (0xC3)
        # Enable the FPGA parallel video interface.
        if not skip_FPGA_video:
            self.__i2c_write(0xC3, [0x01])  
            print(f"prallel video settings: {bin(self.__i2c_read(0xC4,1)[0])}")

        # Write actuator orientation (0xC8)  # TODO: figure out if this one is really needed
        # see DLPC1438 programming guide for interpetation of these bytes. For now just using values of Elegoo board.
        self.__i2c_write(0xC8, [0x03, 0x16, 0x11, 0x06, 0x01])  
        print(f"Actuator orientation settings: {[hex(val) for val in self.__i2c_read(0xC9,5)]}")


    def  __await_SYS_RDY(self):
        while not GPIO.input(self.SYS_RDY):
            time.sleep(0.3)
            print("waiting for SYS_RDY")


    def expose_pattern(self, exposed_frames, dark_frames=5):
        """
        Start exposure of the buffer available to FPGA with a specified number of exposed frames.

        The FPGA outputs a ~60Hz parallel vide signal, so the exposure time (in sec) is roughly the
        number of exposed frames divided by 60. Note that you can also configure
        the exposure to continue indefinitely until the stop_exposure() command is called, by sending
        -1 as the number of exposed frames.

        Taking 5 dark frames is recommended if you call this command just after swapping image
        buffer. If you are doing other operations that take and equivalent amount of time
        after swapping the buffer before calling this function you could set this number to 0
        to increase frame throughput.
        """
        assert GPIO.input(self.SYS_RDY), "SYS_RDY signal is not high yet, cannot expose frames yet."
        assert isinstance(dark_frames, int), "dark_frames must be a 16-bit integer"
        assert 0 <= dark_frames < 65536, "dark_frames must be 16-bit (i.e. in range [0, 65535])"

        if exposed_frames > 0:
            assert isinstance(exposed_frames, int), "exposed_frames must be a 16-bit integer"
            assert 0 <= exposed_frames < 65536, "exposed_frames must be 16-bit (i.e. in range [0, 65535])"

            # start exposure of current buffer for the duration specifed in exposure time
            print(f"> Starting UV exposure (for {exposed_frames} frames / {exposed_frames/60:.2f}sec)!")
            frame_data = [0x00] + \
                list(dark_frames.to_bytes(2, byteorder = 'little')) + \
                list(exposed_frames.to_bytes(2, byteorder = 'little'))
            self.__i2c_write(0xC1,frame_data )
            # the value above never seem to be read back correctly if you read over I2C. Also on anyubic board.'

        elif exposed_frames == -1:
            # start exposure of current buffer for infinite duration with 5 dark frames to let video data stabilise)
            print("> Starting UV exposure (Infinite Duration)!")
            self.__i2c_write(0xC1, [0x00]
                              + list(dark_frames.to_bytes(2, byteorder = 'little'))
                              + [0xFF, 0xFF])  
            # the value above never seem to be read back correctly if you read over I2C. Also on anyubic board.'

        else:
            raise Exception("Invalid exposure time value provided. Value must be positive or -1.")

        time.sleep(0.02) # TODO: optimise delay time; now this is just quick empirical test
        if not GPIO.input(self.PRINT_ACTIVE): warnings.warn("PRINT ACTIVE did not go high after starting exposure. Something might be wrong.") 

    def stop_exposure(self):
        """
        Stop the UV exposure in external print mode
        
        This command is used to stop exposure in case the projector is set to 'indefinite' mode
        in the expose_pattern() command. This then allows the controller (e.g. raspberry pi) to
        control the start and stop time, rather than the DLPC1438. Can be useful in dynamic
        exposure settings, where the total exposure time is not known in advance.

        An alternative way to turn off the projector in indefinite projection mode is to turn
        it to standby mode, but that is not always the desired method.
        """

        print("Stopping UV exposure immediately!")
        self.__i2c_write(0xC1, [0x01, 0x00, 0x00, 0x00, 0x00])  

        time.sleep(0.1) # TODO: optimise delay time; now this is just quick empirical test
        if GPIO.input(self.PRINT_ACTIVE): warnings.warn("PRINT ACTIVE is still high after sending STOP uv expose command. Something might be wrong") 

    def __rowcol_data_block(self, col_start, col_end, row_start):
        """
        Format 4 byte data block containing column start/end and row start information for
        SPI transmission format of DLPC1438.
        """
        # the final 4 bits need to be 1 for reasons not explained, but let's just follow
        # the programmer's guide of DLPC1438
        rowcol_data_block_raw = col_start + (col_end << 5) + (row_start << 10) + (0b1111 << 28)
        rowcol_data_block = list(rowcol_data_block_raw.to_bytes(4, byteorder = 'little'))
        return  rowcol_data_block

    def single_spi_transmission(col_start, col_end, row_start, pixel_data):
        """
        Format and send SPI transmission for an image specified in pixel_data and with frame
        offsets, where the entire image fits in the SPI buffer. For the more general and likely case
        where it does not, have a look at split_spi_transmission()
        """

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
        preamble = [0x04] + rowcol_data_block + [0x00] + list(length.to_bytes(4, byteorder = 'little')) 
        data = preamble + pixel_data.tolist() + [0x00, 0x00, 0x00, 0x00]  # 4 CRC bytes
        with open("spi.txt", "w") as output:
            output.write(str([bin(val) + " , " for val in preamble]))
        return data

    def split_spi_transmission(self, offset_width, offset_height, pixel_data):
        """
        Format and send (multiple) spi transfers to transfer image data to FPGA buffer.

        Offset width specifies the offset of the image along width in pixels from (top) left of frame.
        Offset height is the same, but for the vertical offset in pixels from top (left) of frame.
        
        Data is sent to the currently inactive buffer.
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
        pad_width_end =  (128 - (img_width +  pad_width_start) % 128)  % 128  # maybe there is a more efficient way to compute this
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

        eff_buffersize = self.SPI_BUFFERSIZE - 10
        
        num_rows = math.floor( ((eff_buffersize) / width) /2 ) * 2  # should be even number

        assert num_rows*width < (self.SPI_BUFFERSIZE - 10)  

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
                print(f"the number of bytes we intedn to send: {padded_data.size}")
                preamble = [0x04] + self.__rowcol_data_block(col_start, col_end, row_start) + [0x00] + list((padded_data.size).to_bytes(4, byteorder = 'little'))
                preamble = np.array(preamble, dtype=np.uint8)

            else:
                # note that following trasnfers do not contain the "length" of the transfer in preambe
                preamble = [0x04] + self.__rowcol_data_block(col_start, col_end, row_start + row_tracker) + [0x00]
                preamble = np.array(preamble, dtype=np.uint8)
                
            row_tracker += int(data.shape[1] / 2)  # divided by 2 because the row_start is in steps of 2 (see SPI format)

            data = data.flatten("F")

            # Add 4 CRC bytes if this is the final transmission
            if transfer_idx == (num_transfers-1):
                # Note that CRC bytes are still needed even if you do not use CRC calculation.
                # Note also that the TI programmer's guide is wrong on this matter (it says it should be 2 bytes)
                data = np.append(data, np.array([0x00,0x00,0x00,0x00], dtype=np.uint8)) 

            # Note that xfer3 has a max number of bytes it can transfer set in /sys/module/spidev/parameters/bufsiz
            self.spi.writebytes2(np.insert(data, 0, preamble))  # send transmission over spi

        print(f"SPI transfer took, {time.time()-SPI_start} seconds. At {self.spi.max_speed_hz}Hz clock.")

    def set_background(self, intensity, both_buffers=False):
        '''
        Send constant intensity values for all pixels to the inactive buffer.

        Utility function that allows you to define a static background color to draw images
        on top of with partial draws, or to for example initialise all the framebuffers
        to black(0) or white (255).

        If `both_buffers` is True, the value will be written to both buffers. Will take approximately
        twice as long to complete.
        '''

        assert isinstance(intensity, int), "background intensity value must be an 8-bit integer"
        assert 0 <= intensity < 256, "Intensity must be [0, 255]"

        print(f"> Setting all pixels in current SPI buffer to intensity:{intensity}")
 
        # yes, np.transpose(np.ones(y,x)) transfers faster than np.onex(x,y)
        # I agree it feels a bit silly
        pxldata = np.transpose((np.ones((1440, 2560))*int(intensity)).astype(np.uint8))
        print(f"background image dimensions: {pxldata.shape}")

        self.split_spi_transmission(0, 0, pxldata)  

        # if you want to set the intensity to both buffers
        if both_buffers:
            self.swap_buffer()
            self.set_background(intensity, False)

    
    def send_pixeldata_to_buffer(self, pixeldata, xoffset, yoffset):  
        '''
        Send a 2D array of pixeldata to the inactive buffer at the specified pixel offset
        in x and y.

        Main image display function that takes an np.array of dtype uint8, and sends it
        over to the inactive buffer (i.e. the buffer that is not currently received on DMD).
        Image position offsets are specified in pixels. Note that this function does
        not display data sent; it merely loads into into the inactive buffer and requires
        a buffer swap and expose command to actually be used.
        '''

        assert pixeldata.ndim == 2, "pixeldata must be a 2-dimensional array"
        assert pixeldata.dtype == np.uint8, "pixeldata array must be a uint8 (datatype) array"

        print("> Sending array data over SPI... (SPLIT TECHNIQUE)")

        self.split_spi_transmission(xoffset, yoffset, pixeldata)

    def send_image_to_buffer(self, filename, xoffset, yoffset):  
        '''
        Send an image's pixel data to the inactive buffer at the specified pixel offset
        in x and y.

        Main image display function that takes an 8-bit grayscale image as input, and sends it
        over to the inactive buffer (i.e. the buffer that is not currently received on DMD).
        Image position offsets are specified in pixels. Note that this function does
        not display image sent; it merely loads into into the inactive buffer and requires
        a buffer swap and expose command to actually be used.
        '''

        print("> Sending Image Data over SPI... (SPLIT TECHNIQUE)")
        pxldata = image_to_arr(filename)

        self.split_spi_transmission(xoffset, yoffset, pxldata)
    
    def swap_buffer(self):
        '''
        Swap the inactive buffer (where SPI data goes to) and the active buffer (displayed on DMD).

        The FPGA has two buffers (0 and 1) that are in active or inactive state. If one buffer is
        active (can be queried with I2C), the other one is inactive. The active buffer is 
        sent over the the DMD, while any data sent over SPI to the DMD ends up in the inactive
        buffer. 
        
        Displaying new data will always involve writing to the inactive buffer and
        then swapping buffers to make the inactive buffer the active buffer.
        '''

        # swap the image buffer to make our SENT SPI data available to FPGA and have
        # the other buffer available for SPI writing
        self.SPI_BUFFER_INDEX = not self.SPI_BUFFER_INDEX
        self.__i2c_write(0xC5, [self.SPI_BUFFER_INDEX])  
        print(f"Swapped buffer. The active buffer index is now: {self.__i2c_read(0xC6,1)[0]}")

    def test_FPGA(self):
        """
        Debugging functions for the FPGA. 
        
        NOT Compatible with command 0xC3. Run configure_external_print() with skip_FPGA_video if
        you want to run these commands and see the test pattern.
        """
        FPGA_version = self.__i2c_read(0x64,4)
        print(f"FPGA version: {[bin(val) for val in FPGA_version]}")

        FPGA_status = self.__i2c_read(0x6F,2)
        print(f"FPGA status: {[bin(val) for val in FPGA_status]}")


        print(f"prallel video settings: {bin(self.__i2c_read(0xC4,1)[0])}")

        self.__i2c_write(0x67, [0b00000011, 0x0B]) 
        print(f"FPGA testpattern settings: {[hex(val) for val in self.__i2c_read(0x68,2)]}")

        if not GPIO.input(self.SPI_RDY): warnings.warn("FPGA not ready to receive SPI data")