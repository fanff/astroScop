import asyncio
import concurrent

import websockets
import logging

from time import sleep
from picamera import PiCamera
import time

import logging
from io import BytesIO
from PIL import Image
import json
import os

continueLoop=False


freshParams=None

import imgutils
from rootserver import makeMessage, MsgBuff

serverConnection = None




IMGBUFF = MsgBuff(20)


def cleanParams(params):
    if params == None :
        return {
            "shutterSpeed": 150000,
            "isovalue": 100,
            "redgain": 1.0 ,
            "bluegain": 1.0,
            "expomode": "off",
            "shootresol":{ "width":480,"height":368},
            "dispresol":{ "width":480,"height":368},
            "capture_format":"rgb", # or yuv
            "exposure_compensation":0,

            "brightness":50,
            "saturation":0,
            "contrast":0,
            "save_format":"none",
            "save_section":"test",
            "save_subsection":"",
        }
    else:
        params["shutterSpeed"]
        params["isovalue"]
        params["redgain"]
        params["bluegain"]
        params["expomode"]
        return params

async def cameraLoop():

    global continueLoop
    global freshParams
    await asyncio.sleep(1)
    

    while True: 
        try:
            log = logging.getLogger("cameraLoop")
            
            params = cleanParams(freshParams)
            shootresol = params["shootresol"]
            strtResolution = (shootresol["width"],shootresol["height"])

            log.info("OpeningCamera at resol %s",(strtResolution,))
            with PiCamera(resolution=strtResolution, framerate_range=(0.1,30)) as camera:
                log.info("got camera")
                
                continueLoop=True
                while continueLoop:
                    params = cleanParams(freshParams)
                    shootresol = params["shootresol"]
                    dispresol = (params["dispresol"]["width"],params["dispresol"]["height"])
                    if (shootresol["width"]!=strtResolution[0]):
                        log.info("resolution changed!")
                        break;
                    log.info("looping %s",params)
                    
                    capture_format = params["capture_format"]

                    # setting camera config
                    camsetting_start = time.time()


                    camera.iso = params["isovalue"]
                    camera.brightness = params["brightness"] 
                    camera.contrast = params["contrast"] 
                    # camera.analog_gain=1.0 
                    camera.exposure_mode = params["expomode"]
                    camera.exposure_compensation = params["exposure_compensation"]
                    camera.saturation = params["saturation"]
                    
                    camera.shutter_speed =params["shutterSpeed"]
                    
                    
                    log.info("setting awb_mode off")
                    camera.awb_mode = 'off'
                    
                    g=(params["redgain"],params["bluegain"])
                    camera.awb_gains = g
               
                    camsetting_dur = time.time()-camsetting_start



                    log.info("create databuff")
                    if(capture_format in ["yuv"]):
                        stream = open("/dev/shm/lol.data","w+b")
                    else:
                        stream = BytesIO()

                    log.info("capture start capture_format:%s",capture_format)
                    triggerDate = time.time()
                    camera.capture(stream,format=capture_format,use_video_port=False)
                
                    capture_dur = time.time()-triggerDate
                    
                    
                    # into pill
                    log.info("reading image")
                    strtTime = time.time()
                    if (capture_format == "jpeg"):
                        stream.seek(0)
                        image = Image.open(stream)

                    elif(capture_format=="yuv"):
                        stream.seek(0)
                        rgb = imgutils.yuvbytesToRgb(stream,*strtResolution)
                        image = Image.fromarray(rgb)
                    elif(capture_format=="rgb"):
                        stream.seek(0)
                        image = Image.frombytes("RGB",strtResolution,stream.getvalue(),"raw","RGB",0,1)
                        #image = Image.frombuffer("RGB",strtResolution,stream,"raw","RGB",0,1)
                    pil_dur = time.time()-strtTime
                    
                    
                    #log.info(image.size)
                    strtTime = time.time()
                    #histData = imgutils.colorHist(image)
                    hist_dur = time.time()-strtTime


                    log.info("resizing")
                    strtTime = time.time()
                    imageDisplay = imgutils.resizeImage(image,dispresol)
                    resize_dur = time.time()-strtTime
                    
                    # save original image 
                    strtTime = time.time()
                    save_format = params["save_format"]
                    save_section = params["save_section"]
                    save_subsection = params["save_subsection"]

                    if save_format in ["none",]:
                        pass
                    else:
                        IMGBUFF.stack((image,
                                save_format,save_section,save_subsection,triggerDate))

                    save_dur = time.time()-strtTime
                    

                    # publish image to server
                    usedParams = {
                        "triggerDate": triggerDate,
                        "gains": [float(_) for _ in camera.awb_gains],
                        "analog_gain": float(camera.analog_gain),
                        "iso": camera.iso,
                        "brightness": camera.brightness,
                        "saturation": camera.saturation,
                        "contrast": camera.contrast,
                        "exposure_compensation": camera.exposure_compensation,
                        "resolution": list(strtResolution),
                        "imageSize": image.size,
                        "shutterSpeed": camera.shutter_speed,
                        "exposure_speed": camera.exposure_speed,
                        "exposure_mode": camera.exposure_mode,
                        "awb_mode": camera.awb_mode,

                        "capture_format": capture_format,
                        "save_format": save_format,
                        "save_section": save_section,


                        "camsetting_dur": camsetting_dur,
                        "capture_dur": capture_dur,
                        "pil_dur": pil_dur,
                        "hist_dur": hist_dur,
                        "resize_dur": resize_dur,
                        "save_dur": save_dur,
                    }

                    strtTime = time.time()
                    if serverConnection :
                        try:
                            data = imgutils.pilimTobase64Jpg(imageDisplay)
                            msg=json.dumps({
                                "usedParams":usedParams,
                                "msgtype":"srcimage",
                                "imageData":data})
                            await serverConnection.send(msg)
                        except Exception as e:
                            log.exception("err %s",e)
                    else:
                        log.info("no server")
                    # end sending
                    send_dur = time.time()-strtTime

                    # now send timing data
                    timingData ={
                            "triggerDate":triggerDate,
                            "imgbuffcount" : len(IMGBUFF.content),
                            "send_dur":send_dur,
                            "usedParams":usedParams
                            }

                    msg = ",".join(["%s: %.2f"%(k,timingData[k]) for k in sorted(timingData.keys()) if "dur" in k])
                    log.info("timing info %s , %s in buff",msg,len(IMGBUFF.content))
                    
                    if serverConnection :
                        msg = makeMessage("camTiming",timingData,jdump=True)
                        await serverConnection.send(msg)
                    await asyncio.sleep(.0001)
                # end while 
                log.info("ending capture loop, camera will be reopened")

            #end with camera
            #no camera here

            log.info("camera closed")
        except Exception as e:
            log.exception("whooops")
            await asyncio.sleep(1)


async def wsclient(uri):

    global serverConnection 
    global freshParams 
    log=logging.getLogger("wsclient")
    log.info("Connected to server")

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                #await websocket.send("Hello world!")
                serverConnection = websocket
                while True:
                    data = await websocket.recv()
                    #log.info("got message %s",data)

                    msg=json.loads(data)

                    if msg["msgtype"]== "params":
                        freshParams = msg["data"]
                    else:
                        log.warning("received type %s",msg["msgtype"])


        except Exception as e:
            log.exception("websocket disconnected %s",str(e))
            serverConnection = None
        
        sleepdur = 1
        log.info("reconnecting websocket in %s",sleepdur)
        await asyncio.sleep(sleepdur)

async def bgjob():
    log = logging.getLogger("bgjob")
    sleepdur = 1

    # initiate imgSaver
    imgSaver = imgutils.ImgSaver("./savedimgs/")
    while True:
        log.info("bgjob")

        if len(IMGBUFF.content)>0:
            imgToWrite,save_format, save_section, save_subsection, triggerDate = IMGBUFF.pop()
            loop = asyncio.get_running_loop()

            def blocking_io():
                fdest, fileNameExt = imgSaver.save(imgToWrite,
                                                   save_format, save_section, save_subsection, triggerDate)

                log.info("saving to %s %s", fdest, fileNameExt)
                return fdest, fileNameExt


            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(
                    pool, blocking_io)




        else:
            # wait for image
            await asyncio.sleep(sleepdur)

async def main():


    task1 = asyncio.create_task(wsclient('ws://localhost:8765/camera'))
    task2 = asyncio.create_task( cameraLoop())
    task3 = asyncio.create_task( bgjob())
    
    await task1
    await task2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)
    asyncio.run(main())

