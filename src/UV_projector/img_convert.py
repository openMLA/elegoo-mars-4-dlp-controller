from PIL import Image
import numpy as np


def image_to_arr(path):
    # TODO: run checks on image bit depth and so on

    print("-- Converting image to bytes --")
    im_frame = Image.open(path)
    pixeldata = np.transpose(np.array(im_frame))

    return  pixeldata
