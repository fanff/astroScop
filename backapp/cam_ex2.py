import asyncio
import websockets
import logging

from time import sleep
from picamera import PiCamera
import time
import imgutils
#pports 1080p @ 30fps, 720p @ 60fps and 640x480p 60/90 Recording
import logging
from io import BytesIO
from PIL import Image
import json
import os

continueLoop=False
freshParams=None

serverConnection = None

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
        "capture_format":"rgb",
        "exposure_compensation":"0",

        "brightness":50,
        "saturation":"0",
        "save_format":"none",
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
            log.info("openingcamera")
            
            params = cleanParams(freshParams)
            shootresol = params["shootresol"]
            strtResolution = (shootresol["width"],shootresol["height"])
            with PiCamera(resolution=strtResolution, framerate_range=(0.1,30)) as camera:
                log.info("got camera")
                # Set ISO to the desired value
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

                    camera.iso = params["isovalue"]
                    #log.info("analog_gain %s",camera.analog_gain)
                    camera.brightness = params["brightness"] 
                    #camera.analog_gain=1.0 
                    camera.exposure_mode = params["expomode"]
                    camera.exposure_compensation = params["exposure_compensation"]
                    camera.saturation = params["saturation"]
                    
                    camera.shutter_speed =params["shutterSpeed"]
                    #log.info("exposure speed %s" , camera.exposure_speed)
                    
                    g=(params["redgain"],params["bluegain"])

                    camera.awb_mode = 'off'
                    camera.awb_gains = g
                    # Finally, take several photos with the fixed settings
                
                    #log.info("capture start")
                    
                    if(capture_format in ["yuv"]):
                        stream = open("/dev/shm/lol.data","w+b")
                    else:
                        stream = BytesIO()

                    triggerDate = time.time()
                    camera.capture(stream,format=capture_format)
                
                    capture_dur = time.time()-triggerDate
                    
                    
                    # into pill
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
                    imageDisplay = image.resize(dispresol)
                    resize_dur = time.time()-strtTime
                    
                    # save
                    strtTime = time.time()
                    save_format = params["save_format"]
                    save_section = params["save_section"]
                    save_subsection = params["save_subsection"]
                    fileName = "img_%.6f"%triggerDate
                    fileName=fileName.replace(".","_")
                    if save_format == "none":
                        
                        fdest="none"
                        fileNameExt="none"
                    elif save_format == "tiff":
                    
                        fileNameExt = "%s.tiff"%fileName
                        prefix="./savedimgs/"

                        if len(save_subsection) >0:
                            fdest = os.path.join(prefix,save_section,save_subsection)
                        else:
                            fdest = os.path.join(prefix,save_section)

                        os.makedirs(fdest,exist_ok=True)
                        fileDest = os.path.join(fdest,fileNameExt)
                        image.save(fileDest)
                        log.info("saving to %s",fileDest)

                    save_dur = time.time()-strtTime
                    
                    strtTime = time.time()
                    try:
                        data = imgutils.pilimTobase64Jpg(imageDisplay)
                        msg=json.dumps({
                            "usedParams":{
                                "triggerDate": triggerDate,
                                "gains" :[float(_) for _ in camera.awb_gains],
                                "analog_gain":float(camera.analog_gain), 
                                "iso" :camera.iso,
                                "brightness":camera.brightness,
                                "saturation":camera.saturation,
                                "exposure_compensation":camera.exposure_compensation,
                                "resolution":list(strtResolution),
                                "imageSize":image.size,
                                "shutterSpeed":camera.shutter_speed,
                                "exposure_speed":camera.exposure_speed,
                                "exposure_mode":camera.exposure_mode,
                                "awb_mode":camera.awb_mode,
                                "capture_dur":capture_dur,
                                "pil_dur":pil_dur,
                                "resize_dur":resize_dur,
                                "save_dur":save_dur,
                                "capture_format":capture_format,
                                "save_format":save_format,
                                "save_section":save_section,
                                "fdest":fdest,
                                "fileNameExt":fileNameExt,
                                
                                
                                },
                            "msgtype":"srcimage",
                            "imageData":data})
                        if serverConnection :
                            await serverConnection.send(msg)
                        else:
                            log.info("no server")
                    except Exception as e:
                        log.exception("err %s",e)
                    # end sending

                    dur = time.time()-strtTime
                    log.info("%.2f: capture %.2f; pil %.2f; resize %.2f; save %.2f; sendl %.2f",triggerDate,capture_dur,pil_dur,resize_dur,save_dur,dur)
                    await asyncio.sleep(.0001)
        except Exception as e:
            log.exception("whooops")
            await asyncio.sleep(1)


async def hello(uri):
    async with websockets.connect(uri) as websocket:
        global serverConnection 
        global freshParams 
        log=logging.getLogger("c")
        log.info("connected")
        #await websocket.send("Hello world!")
        serverConnection = websocket
        while True:
            data = await websocket.recv()
            #log.info("got message %s",data)
            freshParams=json.loads(data)
        # while True:
        # #async for data in websocket: 
        #     data = await websocket.recv()
        #     log.info("got message %s",data)
            
async def bgjob():
    log = logging.getLogger("bgjob")
    sleepdur = 1
    while True:
        log.info("bgjob")
        await asyncio.sleep(sleepdur)

async def main():
    task1 = asyncio.create_task( hello('ws://localhost:8765/camera'))
    task2 = asyncio.create_task( cameraLoop())
    
    await task1
    await task2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)
    asyncio.run(main())

