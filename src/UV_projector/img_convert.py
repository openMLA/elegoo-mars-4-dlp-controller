from PIL import Image
import numpy as np


def image_to_arr(path):
    print("-- Converting image to bytes --")
    im_frame = Image.open(path)
    pixeldata = 255-np.transpose(np.array(im_frame))

    print(pixeldata.shape)
    print(pixeldata)
    print("\n")

    return  pixeldata
