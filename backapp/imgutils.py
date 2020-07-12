import cv2

import numpy as np
from PIL import Image
import io
import base64

def yuvbytesToRgb(yuvbytes,width,height):
    stream = yuvbytes
    # Calculate the actual image size in the stream (accounting for rounding
    # of the resolution)
    fwidth = (width + 31) // 32 * 32
    fheight = (height + 15) // 16 * 16
    # Load the Y (luminance) data from the stream
    Y = np.fromfile(stream, dtype=np.uint8, count=fwidth*fheight).\
            reshape((fheight, fwidth))
    # Load the UV (chrominance) data from the stream, and double its size
    U = np.fromfile(stream, dtype=np.uint8, count=(fwidth//2)*(fheight//2)).\
            reshape((fheight//2, fwidth//2)).\
            repeat(2, axis=0).repeat(2, axis=1)
    V = np.fromfile(stream, dtype=np.uint8, count=(fwidth//2)*(fheight//2)).\
            reshape((fheight//2, fwidth//2)).\
            repeat(2, axis=0).repeat(2, axis=1)
    # Stack the YUV channels together, crop the actual resolution, convert to
    # floating point for later calculations, and apply the standard biases
    YUV = np.dstack((Y, U, V))[:height, :width, :].astype(np.float)
    YUV[:, :, 0]  = YUV[:, :, 0]  - 16   # Offset Y by 16
    YUV[:, :, 1:] = YUV[:, :, 1:] - 128  # Offset UV by 128
    # YUV conversion matrix from ITU-R BT.601 version (SDTV)
    #              Y       U       V
    M = np.array([[1.164,  0.000,  1.596],    # R
                  [1.164, -0.392, -0.813],    # G
                  [1.164,  2.017,  0.000]])   # B
    # Take the dot product with the matrix to produce RGB output, clamp the
    # results to byte range and convert to bytes
    RGB = YUV.dot(M.T).clip(0, 255).astype(np.uint8)

    return RGB
def pilimTobase64Jpg(pilim):
    # convert Pil to JPG data
    b = io.BytesIO()
    pilim.save(b, format="JPEG")
    data = b.getvalue()
    return base64.b64encode(data).decode("utf-8")

def colorHist(pilim):

    open_cv_image = np.array(pilim) 
    ocvim = open_cv_image[:, :, ::-1].copy() 


    chans = cv2.split(ocvim)
    colors = ("b", "g", "r")

    features=[]
    # loop over the image channels
    for (chan, color) in zip(chans, colors):
        hist = cv2.calcHist([chan], [0], None, [256], [0, 256])

        features.extend(hist.reshape(1,256).tolist())
    return features

def makePilIMgs():
    arr = np.random.randint(0,255,(100,100,3))
    im = Image.fromarray(arr,'RGB')
    return im



