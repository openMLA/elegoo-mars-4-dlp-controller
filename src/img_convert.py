from PIL import Image
import numpy as np


def image_to_bytes():
    print("-- Converting image to bytes --")
    im_frame = Image.open('../media/openhardware-128x30.png')
    pixeldata = np.array(im_frame)

    print(pixeldata.shape)
    print(pixeldata)
    print("\n")

    return  np.zeros(128*30).astype(int) # pixeldata.flatten("F")

def format_spi_data(col_start, col_end, row_start):
    
    data = col_start + (col_end << 5) + (row_start << 10) + (0b1111 << 28)
    return data

# ex1 = format_spi_data(0, 17, 0)
# for bonk in ex1.to_bytes(4, byteorder = 'little'):
#     print(hex(bonk))
# print(list(ex1.to_bytes(4, byteorder = 'little')))
# print(bin(ex1))

# bonk = 12
# print(list(bonk.to_bytes(4, byteorder = 'little')))
