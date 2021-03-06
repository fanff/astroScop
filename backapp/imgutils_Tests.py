import unittest
import time
from shutil import rmtree

import PIL
import pandas as pd

import imgutils
from imgutils import makePilIMgs, resizeImage, ImgSaver, findConfigDiff
import numpy as np
import os

import matplotlib.pyplot as plt

def makeStatpng(df,fname,title,testedCols = ["save_format"]):
    plt.ioff()
    fig, axes= plt.subplots(2,1,figsize=(8,5*2))

    df.boxplot(column="dur", by=["srcPixCount"]+testedCols,ax=axes[0])
    df.boxplot(column="pixspeed", by=testedCols,ax=axes[1])
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

        srcResol = (3296,2464)
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

        df["pixspeed"] = (df["srcPixCount"] / df["dur"]) / 10 ** 6
        df.to_pickle("./save.df")
        makeStatpng(df, "resizeSpd.png", "resize Speed",testedCols = ["rgap","modestr"])





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

        expcount = 30
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
        print("writes in ram" )
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

        expcount = 30
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

    def test_realImages_instick(self):
        return
        print("writes in stick" )
        if not os.path.exists("/media/imgstick"):
            return

        rmtree("/media/imgstick/a", ignore_errors=True)
        time.sleep(1)

        saver = ImgSaver("/media/imgstick/")

        # source images
        realimagesNames = ["moon1.jpg", "moon2.jpg", "mars1.png"]

        realimages = [PIL.Image.open("testimgs/%s" % (_,)) for _ in realimagesNames]
        # resols
        srcResols = [(1280, 720), (3296, 2464)]

        expcount = 30
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
        makeStatpng(df, "realinstick.png", "real_in stick")

        rmtree("/media/imgstick/a")


class TC_findConfigDiff(unittest.TestCase):
    def test_1_(self):
        self.assertDictEqual({"a":"n"},findConfigDiff({},{"a":"n"}))
        self.assertDictEqual({}, findConfigDiff({"a": "n"}, {}))

        self.assertDictEqual({},findConfigDiff({"a":"n"},{"a":"n"}))

        self.assertDictEqual({"a": "b"}, findConfigDiff({"a": "n"}, {"a": "b"}))

    def test_2_(self):
        self.assertDictEqual({"a": {"aname": "xd"}},
                             findConfigDiff({"a": {"aname": "lol"}},
                                            {"a": {"aname": "xd"}}))

class TC_histogram(unittest.TestCase):
    def test_1_(self):
        realimagesNames = ["moon1.jpg", "moon2.jpg", "mars1.png"]


        realimages = [PIL.Image.open("testimgs/%s" % (_,)) for _ in realimagesNames]

        res = imgutils.colorHist(realimages[0])

        print(len(res))
        print(len(res[1]))
        print(np.mean(res[0]),np.min(res[0]),np.max(res[0]))

        img:PIL.Image = realimages[0]

        h2 = imgutils.colorHist2(img)
        print(len(h2))

        print(np.mean(h2[0]),np.min(h2[0]),np.max(h2[0]))
    def test_2_(self):
        realimagesNames = ["moon1.jpg", "moon2.jpg", "mars1.png"]


if __name__ == '__main__':
    unittest.main()
