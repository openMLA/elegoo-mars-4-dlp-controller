import RPi.GPIO as GPIO
import time
import smbus  # i2c


GPIO.setmode(GPIO.BCM)

# Pin numbering
PROJ_ON = 5
SYS_RDY = 6
HOST_IRQ = 19

# Configure the pins
GPIO.setup(PROJ_ON, GPIO.OUT)  
GPIO.setup(SYS_RDY, GPIO.IN)  
GPIO.setup(HOST_IRQ, GPIO.IN)  

try:
    # Initialise the DLPC1438
    print("Intialising the DLPC1438...")

    # NOTE: the checks below work the first boot, but something seems to "keep the DLPC1438" turned
    # on, so next time you run it you may need to comment this out. A better solution pending.

    assert not GPIO.input(HOST_IRQ), "HOST_IRQ was high before startup sequence."

    # send the PROJ_ON signal and wait for the HOST_IRQ signal to go high, signalling the DLPC1438
    # is ready to go
    GPIO.output(PROJ_ON, GPIO.HIGH)
    ref_time = time.time()
    while not GPIO.input(HOST_IRQ):
        # pass
        time.sleep(0.1)

    print(f"DLPC1438 is signalling it is ready for use, {time.time()-ref_time} seconds after PROJ_ON went high.")

    ### I2C MATERIAL ------------------
 
    # Initialize I2C (SMBus) on channel 1
    bus = smbus.SMBus(1)
    #  DLPC1438 on Anyubic board address
    DLPC1438 = 0x1B

    mode = bus.read_i2c_block_data(DLPC1438,0x06,1)  # probably standby if just initialised
    print(f"we are in mode: {mode}")

    # switch to testpattern mode
    bus.write_i2c_block_data(DLPC1438, 0x05, [0x01])  # testpattern (seems quite dim in default state)
    mode = bus.read_i2c_block_data(DLPC1438,0x06,1) 
    print(f"are we in tespattern mode? : {mode}")

    # enable flood light
    bus.write_i2c_block_data(DLPC1438, 0x16, [0b00001111])
    time.sleep(3)  # lit for 3s
    bus.write_i2c_block_data(DLPC1438, 0x16, [0b00000000])
    time.sleep(1)  # back to testpattern (dim)

    # and back to standby
    bus.write_i2c_block_data(DLPC1438, 0x05, [0xFF])  # standby
    mode = bus.read_i2c_block_data(DLPC1438,0x06,1) 
    print(f"back in standby? : {mode}")

    GPIO.cleanup()

except KeyboardInterrupt:
    GPIO.cleanup()