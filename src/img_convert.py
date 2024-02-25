from PIL import Image
import numpy as np


def image_to_bytes():
    print("-- Converting image to bytes --")
    im_frame = Image.open('../media/openMLA_logo_256x144.png')
    pixeldata = 255-np.transpose(np.array(im_frame))

    print(pixeldata.shape)
    print(pixeldata)
    print("\n")

    return pixeldata.flatten("F") # np.ones(512*64).astype(int) 

def format_spi_data(col_start, col_end, row_start):
    
    data = col_start + (col_end << 5) + (row_start << 10) + (0b1111 << 28)
    return data

