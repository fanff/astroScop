import cv2

import numpy as np
from PIL import Image
import io
import base64

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


