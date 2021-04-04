import PIL
import cv2

import numpy as np
from PIL import Image
import io
import base64

import time
import os


class ImgSaver():
    def __init__(self,prefix):
        self.prefix = prefix
    
    def fileNameExt(self,save_format,save_section,save_subsection,triggerDate):
        """
        destfolder +
        file name with extentions"""
        fileName = "img_%.6f"%triggerDate
        fileName=fileName.replace(".","_")
        
        formatToExt = {"jpg":"jpg","tiff":"tiff","bmp":"bmp"}

        fileNameExt = "%s.%s"%(fileName,formatToExt[save_format])

        if len(save_subsection) >0:
            fdest = os.path.join(self.prefix,save_section,save_subsection)
        else:
            fdest = os.path.join(self.prefix,save_section)

        return fdest,fileNameExt


    def save(self,img,save_format,save_section,
             save_subsection,triggerDate):
        strtTime = time.time()

        fileName = "img_%.6f"%triggerDate
        fileName=fileName.replace(".","_")
        if save_format in ["tiff","jpg","bmp"]:
            
            fdest,filenameExt = self.fileNameExt(save_format,save_section,save_subsection,triggerDate)
            os.makedirs(fdest,exist_ok=True)
            fileDest = os.path.join(fdest,filenameExt)
            img.save(fileDest)
            return fdest,filenameExt
        else:
            fdest="none"
            filenameExt="none"

            return fdest,filenameExt


        save_dur = time.time()-strtTime
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
    """

    """
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

def makePilIMgs(resol=(100,100)):
    """
    make image from random numbers
    """
    arr = np.random.randint(0,255,(resol[0],resol[1],3))
    im = Image.fromarray(arr,'RGB')
    return im


if int(PIL.Image.__version__[0])<=5:
    def resizeImage(image:Image,newresol,
                    resample=PIL.Image.NEAREST,reducing_gap=1.0):
        """
        BICUBIC
        NEAREST
        """
        return image.resize(newresol,resample=resample)

else:

    def resizeImage(image:Image,newresol,
                    resample=PIL.Image.NEAREST,reducing_gap=1.0):
        """
        BICUBIC
        NEAREST
        """
        return image.resize(newresol,resample=resample,
                            reducing_gap=reducing_gap)



def findConfigDiff(existing,newp):

    newVals = {}
    for k,v in newp.items():
        if k in existing:
            if v==existing[k]:
                pass
            else:
                newVals[k]=v

        else:
            newVals[k] = v
    return newVals

