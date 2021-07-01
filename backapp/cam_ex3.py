
import asyncio
import concurrent

import websockets
import logging

import time
import picamerax
import numpy as np
from picamerax.array import PiRGBAnalysis
from picamerax.color import Color


import logging

from io import BytesIO
from PIL import Image
import json
import os
import imgutils
from rootserver import makeMessage, MsgBuff
import datetime

continueLoop=True
freshParams=None

newFreshParams = True

IMGBUFF = MsgBuff(1)
TOSAVEBUFF = MsgBuff(600)


serverConnection= None
serverOverwhelmed = False



async def continuousRecording(camera,analyzer):
    global continueLoop
    global newFreshParams

    try:
        while continueLoop:
            camera.wait_recording(.001)
            await asyncio.sleep(.001)


            if newFreshParams:
                newps = cleanParams(freshParams)


                alldiff = imgutils.findConfigDiff(analyser.params, newps)

                if "shootresol" in alldiff or "capture_format" in alldiff:
                    continueLoop = False
                else:
                    analyzer.params = newps
                    log.info("new Fresh Params: %s",newFreshParams)
                    setParamsToCamera(camera,newps)
                    newFreshParams = False


    except Exception as e:
        log.exception("error in recording")
    finally:
        camera.stop_recording()



class JPGOutput(object):
    def __init__(self,params):
        pass
        self.params = {}

    def write(self, buf):
        triggerDate = time.time()
        if buf.startswith(b'\xff\xd8'):
            p = self.params.copy()

            IMGBUFF.stack((buf,p,triggerDate))

class MyAnalyser(PiRGBAnalysis):
    """
    RGB Analyser
    """
    def __init__(self, camera,params):
        super(MyAnalyser, self).__init__(camera)
        self.params = params
        self.cam = camera


    def analyze(self, a):
        """
        """
        triggerDate = time.time()
        g = self.cam.awb_gains 
        usedparams = {
            "triggerDate":triggerDate,
            "triggerDateStr":str(datetime.datetime.utcnow()),
            "shutterSpeed": str(self.cam.shutter_speed),
            "isovalue": self.cam.iso,
            "redgain":float( g[0]),
            "bluegain": float(g[1]),
            "expomode": self.cam.exposure_mode,
            "shootresol":{ "name":str(a.shape) , "width":a.shape[1],"height":a.shape[0]},
            "exposure_compensation":self.cam.exposure_compensation,
            "brightness":self.cam.brightness,
            "saturation":self.cam.saturation,
            "contrast":self.cam.contrast,


            "sensor_mode" : self.cam.sensor_mode,
            "sharpness" : self.cam.sharpness,
            "video_denoise" : self.cam.video_denoise,
            "video_stabilization" : self.cam.video_stabilization,
            "zoom" : str(self.cam.zoom),
            "revision" : str(self.cam.revision),
            "resolution" : str(self.cam.resolution),
            "digital_gain" : str(float(self.cam.digital_gain)),

            "analog_gain" : str(float(self.cam.analog_gain)),
                }
        

        p = self.params.copy()
        p.update(usedparams)

        IMGBUFF.stack((a,p,triggerDate))
        
        #print("stacked , %s"%len(IMGBUFF.content))



defaultconfig = {
        "shutterSpeed": 150000,
        "isovalue": 100,
        "redgain": 1.0 ,
        "bluegain": 1.0,

        "digital_gain": 1.0,
        "analog_gain": 1.0,
        "expomode": "off",
        "shootresol":{ "name":"default", "width":480,"height":368,"mode":0},
        "dispresol":{ "name":"default","width":480,"height":368,"mode":0},

        "denoise":False,
        "capture_format":"rgb", # or yuv
        "exposure_compensation":0,

        "brightness":50,
        "saturation":0,
        "contrast":0,
        "sharpness":0,
        "save_format":"none",
        "save_section":"test",
        "save_subsection":"",
        "cameraZoom":0,
        "crop":(0,0,1,1),

}

mandatoryKeys = set(defaultconfig.keys())
def cleanParams(params):

    if params == None :
        return defaultconfig
    else:
        for k in mandatoryKeys:
            if k not in params:
                params[k] = defaultconfig[k]
        return params

def setParamsToCamera(camera,params):
    log = logging.getLogger("setParams")
    camera.iso = params["isovalue"]
    camera.brightness = params["brightness"]
    camera.contrast = params["contrast"]
    camera.saturation = params["saturation"]
    camera.sharpness = params["sharpness"]
    camera.shutter_speed = params["shutterSpeed"]
    camera.exposure_mode = params["expomode"]

    camera.exposure_compensation = params["exposure_compensation"]

    camera.awb_mode = 'off'
    g = (params["redgain"], params["bluegain"])
    camera.awb_gains = g

    camera.digital_gain = params["digital_gain"]
    camera.analog_gain = params["analog_gain"]

    camera.video_denoise = params["denoise"]

    if params["cameraZoom"] != 0:
        camera.zoom = tuple(params["crop"])
    else:
        camera.zoom = (0,0,1,1)

async def openCamera(params):
    global continueLoop
    global newFreshParams
    try:
        
        log = logging.getLogger("openCam")

        shootresol = params["shootresol"]
        strtResolution = (shootresol["width"],shootresol["height"])
        sensor_mode = shootresol["mode"] 
        capture_format = params["capture_format"]
        
        log.info("OpeningCamera at resol %s mode:%s capture_format: %s",strtResolution,
                sensor_mode,
                capture_format)


        with picamerax.PiCamera(resolution=strtResolution, 
                framerate_range=(0.01,30),sensor_mode=sensor_mode) as camera:

            setParamsToCamera(camera, params)
            
            if params["capture_format"] == "rgb":
                with MyAnalyser(camera,params) as analyzer:

                    camera.start_recording(analyzer, 'rgb')
                    await continuousRecording(camera,analyser)

            elif params["capture_format"] == "jpeg":

                out = JPGOutput(params)
                camera.start_recording(out, 'mjpeg')

                await continuousRecording(camera,out)

    except Exception as e:
        log.exception("whoaaw error %s"%str(e))

async def cameraLoop():

    global continueLoop
    global freshParams
    global newFreshParams
    await asyncio.sleep(1)
    
    log = logging.getLogger("cameraLoop")


    while True: 

        try:
            params = cleanParams(freshParams)
            newFreshParams = False 
            continueLoop=True
            await openCamera(params) 


            log.info("camera closed")
        except Exception as e:
            log.exception("whooops")
            await asyncio.sleep(1)

async def wsclient(uri):

    global serverConnection 
    global serverOverwhelmed 
    global freshParams 
    global newFreshParams
    
    log=logging.getLogger("wsclient")
    log.info("Connected to server")

    while True:
        try:
            async with websockets.connect(uri,
                    ping_interval=3, ping_timeout=3, close_timeout=3, 
                    ) as websocket:
                #await websocket.send("Hello world!")
                serverConnection = websocket
                while True:
                    data = await websocket.recv()
                    #log.info("got message %s",data)

                    msg=json.loads(data)

                    if msg["msgtype"]== "params":
                        freshParams = msg["data"]
                        
                        newFreshParams = True
                        log.info("received new fresh params")
                    elif msg["msgtype"]== "serverOverwhelmed":
                        serverOverwhelmed = msg["data"]
                        log.debug("received overwhelmed %s",msg["data"])
                    else:
                        log.warning("received type %s",msg["msgtype"])


        except websockets.exceptions.ConnectionClosed as e:
            serverConnection = None

        except concurrent.futures._base.CancelledError as e:
            log.info("quit due to cancelled Error")
        except Exception as e:
            log.exception("websocket disconnected %s",str(e))
            serverConnection = None
        
        sleepdur = 1
        log.info("reconnecting websocket in %s",sleepdur)
        await asyncio.sleep(sleepdur)



async def bgjob():
    """
    use the IMGBUFF global object

    """
    global serverConnection 
    global serverOverwhelmed 

    log = logging.getLogger("imgForwd")
    sleepdur = .1
    lastTimingSend   = 0
    while True:
        try:
            if len(IMGBUFF.content)>0:
                a,params, triggerDate = IMGBUFF.pop()

                save_format = params.get("save_format","none")
                save_section = params.get("save_section","work")
                save_subsection = params.get("save_subsection","")

                if save_format not in ["none"]:
                    TOSAVEBUFF.stack((a,params, triggerDate))

                if not serverOverwhelmed:
                    log.debug("bgjob with %s objects in buff ",len(IMGBUFF.content))
                    log.debug("will send to server")

                    if "capture_format" in params and params["capture_format"]=="jpeg":
                        image = Image.fromstring(a)
                    else:


                        image = Image.fromarray(a)

                    if serverConnection :
                        try:

                            dispresol = (params["dispresol"]["width"],
                                    params["dispresol"]["height"])

                            log.debug("go for resize b64 json")
                            imageDisplay = imgutils.resizeImage(image,dispresol)
                            data = imgutils.pilimTobase64Jpg(imageDisplay)
                            msg=json.dumps({
                                "usedParams":params,
                                "msgtype":"srcimage",
                                "imageData":data})


                            log.debug("sending to server")
                            await serverConnection.send(msg)
                            await asyncio.sleep(.02) # wait a little

                        except websockets.exceptions.ConnectionClosed as e:
                            serverConnection =False
                            log.error("disconnected with server %s",e)
                        except Exception as e:
                            log.exception("err sending to server %s",e)
                    else:
                        log.info("no server")
                else:
                    log.debug("server has too much work")
                    await asyncio.sleep(.001)
            else:
                # wait for image
                await asyncio.sleep(sleepdur)
            
            if time.time()>lastTimingSend + 3: 
                lastTimingSend = time.time()
                # now send timing data
                timingData ={
                        "imgbuffcount" : len(IMGBUFF.content),
                        "tosavecount" : len(TOSAVEBUFF.content),
                        }

                #msg = ",".join(["%s: %.2f"%(k,timingData[k]) for k in sorted(timingData.keys()) if "dur" in k])
                log.info("some info %s ",timingData)
                
                if serverConnection :
                    msg = makeMessage("camTiming",timingData,jdump=True)
                    await serverConnection.send(msg)
                await asyncio.sleep(.0001)
        except concurrent.futures._base.CancelledError as e:
            log.info("quit due to cancelledError")
            return 
        except KeyboardInterrupt as e:
            log.info("quit due to key interrupt")
            return 
        except Exception as e:
            log.exception("error")


async def savingJob():
    """
    use the IMGBFF global object

    """
    global IMGBUFF
    await asyncio.sleep(.2)
    log = logging.getLogger("savingTask")
    sleepdur = .1
    # initiate imgSaver
    imgSaver = imgutils.ImgSaver("./savedimgs/")
    log.info("saver created ")
    while True:
        try:
            count = len(TOSAVEBUFF.content)
            if count>0:

                log.info("going to save image %s ",count)
                a,params, triggerDate = TOSAVEBUFF.pop()
                
                save_format = params["save_format"]
                save_section = params["save_section"]
                save_subsection = params["save_subsection"]

                if save_format in ["none"]:
                    await asyncio.sleep(0.01)
                else:

                    image = Image.fromarray(a)
                    loop = asyncio.get_running_loop()

                    def blocking_io():
                        logth = logging.getLogger("saveinthread")
                        try:
                            fdest, fileNameExt = imgSaver.save(image,
                                                               save_format,
                                                               save_section, 
                                                               save_subsection,
                                                               triggerDate)

                            #logth.info("saving to %s %s", fdest, fileNameExt)
                            return fdest, fileNameExt
                        except Exception as e:
                            logth.exception("error saving")
                            return "none", "none"


                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = await loop.run_in_executor(
                            pool, blocking_io)
                    await asyncio.sleep(sleepdur)
            else:
                # wait for image
                await asyncio.sleep(sleepdur)

        except Exception as e:
            log.exception("error saving")
            await asyncio.sleep(sleepdur)


async def main():


    task1 = asyncio.create_task(wsclient('ws://localhost:8765/camera'))
    task2 = asyncio.create_task( cameraLoop())
    task4 = asyncio.create_task( savingJob())
    task3 = asyncio.create_task( bgjob())
    
    await task1
    await task2
    await task3
    await task4


if __name__ == "__main__":
    formatstr = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    #formatter = logging.Formatter(formatstr)
    logging.basicConfig(level=logging.INFO,format=formatstr)

    log = logging.getLogger(__name__)
    asyncio.run(main())

