import warnings
import RPi.GPIO as GPIO
import time


# Pin numbering
PROJ_ON = 5
SYS_RDY = 6
HOST_IRQ = 19

#  DLPC1438 on Anyubic board address
DLPC1438_addr = 0x1B

def intialise_DLPC1438(i2c_bus):
    """
    Checks if the DCLP1438 is running and ready for i2c communication, and if not, will 
    start the DLPC1438 with the PROJ_ON gpio signal.
    """
    print("Intialising the DLPC1438...")

    print()

    # Configure the pins
    GPIO.setup(PROJ_ON, GPIO.OUT)  
    GPIO.setup(SYS_RDY, GPIO.IN)  
    GPIO.setup(HOST_IRQ, GPIO.IN)  
        
    # there are 2 options (see figure 9.1 of DLPC1438 datasheet):
    # [1] host_IRQ is low, and the DLPC1438 has not started yet
    # [2] host IRQ is low, but the DLCP1438 is already active and running

    if i2c_bus.read_byte(DLPC1438_addr) != 0:  # check if i2c is already active. Then we are in [2]
        warnings.warn("DLPC1438 is already powered on when script initialised. No startup action needed.")
        return
    else:
        print("Setting PROJ_ON high to start DLPC1438 startup sequence... ")

        # send the PROJ_ON signal and wait for the HOST_IRQ signal to go high, signalling the DLPC1438
        # is ready to go
        GPIO.output(PROJ_ON, GPIO.HIGH)
        ref_time = time.time()
        while not GPIO.input(HOST_IRQ):
            time.sleep(0.1)

        print(f"DLPC1438 is signalling it is ready for use, {time.time()-ref_time} seconds after PROJ_ON went high.")

        # now we need to wait for I2C communication to be ready
        time.sleep(1)  # TODO: make this more robust

        # keep looping as long as we cannot find the DLPC1438 on the i2c bus
        while i2c_bus.read_byte(DLPC1438_addr) == 0:  
            time.sleep(1)

        return
