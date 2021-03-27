import unittest
import time
from shutil import rmtree

import PIL
import pandas as pd
from imgutils import makePilIMgs, resizeImage, ImgSaver
import numpy as np


import matplotlib.pyplot as plt

def makeStatpng(df,fname,title):
    plt.ioff()
    fig, axes= plt.subplots(2,1,figsize=(8,5*2))

    df.boxplot(column="dur", by=["srcPixCount" ,"save_format"],ax=axes[0])
    df.boxplot(column="pixspeed", by=["save_format"],ax=axes[1])
    fig.suptitle(title)
    fig.savefig(fname)



class TC_bench_resizeImage(unittest.TestCase):
    def test_1(self):
        """

        ls:[ {name:"128x64", width:128,height:64},
            {name:"480x368", width:480,height:368},
          {name:"640x480", width:640,height:480},


          {name:"1280x720", width:1024,height:720},
          {name:"1640x1232", width:1640,height:1232},

          {name:"1920x1080", width:1920,height:1080},
          {name:"1920x1088", width:1920,height:1088},
          {name:"3280x2464", width:3280,height:2464},
          {name:"3296x2464", width:3296,height:2464},
        ],
        """


        #srcResol = (3296,2464)
        #targtResol = (1280,720)

        srcResol = (1280,720)
        targtResol = (480,368)


        srcPixCount = srcResol[0]*srcResol[1]
        trgPixCount = targtResol[0] * targtResol[1]
        rgap = None

        expcount = 10



        mods = [
            ["NEAREST", PIL.Image.NEAREST],
            ["BICUBIC",PIL.Image.BICUBIC]]

        rgaps = [None,1.0,2.0,3.0]

        res=[]
        srcimgs = [makePilIMgs(resol=srcResol) for i in range(expcount)]


        for modestr,mod in mods:
            for rgap in rgaps:
                for srcimg in srcimgs:


                    strt = time.time()
                    newimgs = resizeImage(srcimg,targtResol,mod,
                                reducing_gap=None)
                    dur = time.time()-strt
                    res.append([
                        dur,srcResol,targtResol,srcPixCount,trgPixCount,
                        rgap,
                        modestr])
        cols = ["dur","srcResol","targtResol","srcPixCount","trgPixCount",
                        "rgap",
                        "modestr"]
        df = pd.DataFrame(res,columns=cols)

        drr:pd.DataFrame = df[["dur","rgap","modestr"]].groupby(["rgap","modestr"]).mean()

        print(drr)


        print(drr.loc[drr["dur"].idxmin()])


class TC_bench_SaveImage(unittest.TestCase):
    def test_1_randomImages(self):
        saver = ImgSaver("./")
        srcResols = [(1280, 720),(3296, 2464)]



        expcount = 30
        res = []


        save_formats = ["tiff","jpg","bmp"]

        # using random images
        for srcResol in srcResols:
            srcimgs = [makePilIMgs(resol=srcResol) for i in range(expcount)]
            datesrcs = list(range(expcount))


            srcPixCount = srcResol[0] * srcResol[1]
            for save_format in save_formats:

                for srcimg,dt in zip(srcimgs,datesrcs):
                    strt = time.time()
                    saver.save(srcimg,save_format,"a","a",dt)
                    dur = time.time() - strt

                    res.append([
                        dur, srcResol, srcPixCount, save_format
                        ])
                    time.sleep(.1)

        cols = ["dur", "srcResol", "srcPixCount", "save_format"]
        df = pd.DataFrame(res, columns=cols)
        df["pixspeed"] = (df["srcPixCount"] / df["dur"]) / 10 ** 6
        df.to_pickle("./save.df")
        makeStatpng(df, "fakeinlocal.png", "fake in local")


        print(df.groupby(["save_format","srcPixCount"]).mean())

        rmtree("./a")

    def test_2_realImages(self):

        print("version : %s"%PIL.Image.__version__)
        rmtree("./a",ignore_errors=True)
        time.sleep(1)


        saver = ImgSaver("./")

        #source images
        realimagesNames = ["moon1.jpg","moon2.jpg","mars1.png"]

        realimages = [PIL.Image.open("testimgs/%s"%(_,)) for _ in realimagesNames]
        # resols
        srcResols = [(1280, 720), (3296, 2464)]

        expcount = 10
        res = []

        save_formats = ["tiff", "jpg", "bmp"]



        for realimgname , realimg in zip(realimagesNames,realimages):


            for srcResol in srcResols:
                srcimg = resizeImage(realimg,srcResol)
                srcimgs = [srcimg for i in range(expcount)]
                datesrcs = list(range(expcount))

                srcPixCount = srcResol[0] * srcResol[1]
                for save_format in save_formats:

                    for srcimg, dt in zip(srcimgs, datesrcs):
                        strt = time.time()
                        saver.save(srcimg, save_format, "a", str(srcPixCount), dt)
                        dur = time.time() - strt

                        res.append([
                            dur, srcResol, srcPixCount, save_format,realimgname
                        ])
                        time.sleep(.2)

        cols = ["dur", "srcResol", "srcPixCount", "save_format","realimgname"]
        df = pd.DataFrame(res, columns=cols)
        df["pixspeed"] = (df["srcPixCount"] / df["dur"])/10**6
        df.to_pickle("./save.df")
        makeStatpng(df, "realinlocal.png", "real_in /a")

        rmtree("./a",ignore_errors=True)


    def test_2_realImages_inshm(self):
        print("writes in ram" % PIL.Image.__version__)
        if not os.path.exists("/dev/shm/"):
            return

        rmtree("/dev/shm/a", ignore_errors=True)
        time.sleep(1)

        saver = ImgSaver("/dev/shm/")

        # source images
        realimagesNames = ["moon1.jpg", "moon2.jpg", "mars1.png"]

        realimages = [PIL.Image.open("testimgs/%s" % (_,)) for _ in realimagesNames]
        # resols
        srcResols = [(1280, 720), (3296, 2464)]

        expcount = 10
        res = []

        save_formats = ["tiff", "jpg", "bmp"]

        for realimgname, realimg in zip(realimagesNames, realimages):

            for srcResol in srcResols:
                srcimg = resizeImage(realimg, srcResol)
                srcimgs = [srcimg for i in range(expcount)]
                datesrcs = list(range(expcount))

                srcPixCount = srcResol[0] * srcResol[1]
                for save_format in save_formats:

                    for srcimg, dt in zip(srcimgs, datesrcs):
                        strt = time.time()
                        saver.save(srcimg, save_format, "a", str(srcPixCount), dt)
                        dur = time.time() - strt

                        res.append([
                            dur, srcResol, srcPixCount, save_format,realimgname
                        ])
                        time.sleep(.2)

        cols = ["dur", "srcResol", "srcPixCount", "save_format","realimgname"]
        df = pd.DataFrame(res, columns=cols)
        df["pixspeed"] = (df["srcPixCount"] / df["dur"]) / 10 ** 6
        df.to_pickle("./save.df")
        makeStatpng(df, "realinshm.png", "real_in shm")

        rmtree("/dev/shm/a")



if __name__ == '__main__':
    unittest.main()
