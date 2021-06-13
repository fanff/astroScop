import asyncio
import concurrent

import websockets
import logging

import time
import logging

from io import BytesIO
from PIL import Image
import json
import os
import imgutils
from rootserver import makeMessage, MsgBuff
import datetime
from subprocess import call


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
    #gphoto2 --set-config /main/imgsettings/iso=320000
    #gphoto2 --set-config  gphoto2 --set-config /main/capturesettings/shutterspeed=30





def cameraAct(func):
    logth = logging.getLogger("cameraAct")
    try:
        logth.info("hello ? ")
        return func()
    except Exception as e:
        logth.exception("wwww")
        return None




class CameraSequence():
    
    def __init__(self):
        self.seq = []

    def pop(self):
        a = self.seq[0]
        self.seq = self.seq[1:]
        return a

    def push(self,a):
        self.seq.append(a)
    def __len__(self):
        return len(self.seq)
    def clear(self):
        self.seq= []


sequence = CameraSequence()
IMGBUFF = MsgBuff(2)
#sequence.push(("set_param",{"key":"/main/imgsettings/iso","index":14}))

sequence.push(("set_param",{"key":"/main/capturesettings/imagequality","index":0}))
#/main/capturesettings/imagequality
#Label: Image Quality
#Readonly: 0
#Type: RADIO
#Current: RAW
#Choice: 0 Standard
#Choice: 1 Fine
#Choice: 2 Extra Fine
#Choice: 3 RAW
#Choice: 4 RAW+JPEG
#END#
sequence.push(("capture_cli",None))

async def camerahandler(my_cam):
    global sequence
    global IMGBUFF


    log = logging.getLogger("cameraHandler")
    
        
    while True:

        if len(sequence)>0:
            act,params = sequence.pop()

            log.info("action is %s",act)
            #help(my_cam) 

            if act == "capture":
                # put my_cam.lol() in a thread
                """# Capture an image to the camera's RAM and get its data
                imgdata = my_cam.capture()

                # Grab a preview from the camera
                previewdata = my_cam.get_preview()

                # Get a list of files on the camera
                files = tuple(my_cam.list_all_files())"""
                loop = asyncio.get_running_loop()
                
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await asyncio.get_running_loop().run_in_executor(
                            pool, lambda :call(["gphoto2","--trigger-capture"])  )
                log.info("capture done! %s",result)

                sequence.append("capture")
            if act == "capture_cli":
                baseshm = "/dev/shm/work/"
                extension = "jpg"
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await asyncio.get_running_loop().run_in_executor(
                            pool, lambda :call(["gphoto2","--capture-image-and-download"],cwd=baseshm)  )

                imageFileName = "img_%d.%s"%(time.time(),extension)

                cstfilename = "capt0000.%s"%extension
                
                finalName = os.path.join(baseshm,imageFileName)
                os.rename(os.path.join(baseshm,cstfilename),finalName)

                log.info("file in %s",finalName)

                await asyncio.sleep(2)
                sequence.push(("capture_cli",None))
            elif act == "set_param":
                paramkey = params["key"]
                paramindex = params["index"] 
                
                # /main/capturesettings/shutterspeed 
                # /main/imgsettings/iso


                log.info("setting config-index %s=%s" % (paramkey,paramindex))

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await asyncio.get_running_loop().run_in_executor(
                            pool, lambda :call(["gphoto2","--set-config-index","%s=%s"%(paramkey,paramindex) ]) )

                log.info("done setting config")
                #gphoto2 --get-config /main/status/batterylevel
                #gphoto2 --set-config /main/imgsettings/iso=320000
                #gphoto2 --set-config  gphoto2 --set-config 30
            elif act == "getPreview":
                # put my_cam.lol() in a thread

                triggerDate = time.time()
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await asyncio.get_running_loop().run_in_executor(
                        pool, cameraAct,lambda : my_cam.get_preview() )

                IMGBUFF.stack((result, triggerDate))



        else:
            await asyncio.sleep(.1)



async def cameraHold():
    my_cam = None
    log= logging.getLogger("cameraHold")

    while True:
        try:
            await camerahandler(my_cam)

        except Exception as e:
            log.exception("whoops ")
        finally:

            log.debug("will loop in 1 sec ")
            await asyncio.sleep(1)



continueLoop=True
freshParams=None
newFreshParams = True

IMGBUFF = MsgBuff(2)
TOSAVEBUFF = MsgBuff(300)


serverConnection= None
serverOverwhelmed = False

async def wsclient(uri):
    global serverConnection
    global serverOverwhelmed
    global freshParams
    global newFreshParams

    global sequence


    log = logging.getLogger("wsclient")
    log.info("Connected to server")

    while True:
        try:
            async with websockets.connect(uri,
                                          ping_interval=3, ping_timeout=3, close_timeout=3,
                                          ) as websocket:
                # await websocket.send("Hello world!")
                serverConnection = websocket
                while True:
                    data = await websocket.recv()
                    # log.info("got message %s",data)

                    msg = json.loads(data)

                    if msg["msgtype"] == "addInSeq":
                        sequence.append(msg["data"])
                        sequence.push(("capture_cli",None))
                    else:
                        log.warning("unknown message")

        except websockets.exceptions.ConnectionClosed as e:
            serverConnection = None

        except concurrent.futures._base.CancelledError as e:
            log.info("quit due to cancelled Error")
        except Exception as e:
            log.exception("websocket disconnected %s",str(e))
            serverConnection = None

        finally:

            log.debug("will loop in 1 sec ")
            await asyncio.sleep(1)


async def cameraLoop():
    while True:
        # monitor sequence size
        # current action
        # if preview_image available, push it to serv

        if len(IMGBUFF.content)>0:
            # pop

            if serverConnection and not serverOverwhelmed:
                await serverConnection.send(
                    makeMessage("previewImage", None, jdump=True))



        await asyncio.sleep(1)


async def main():
    task1 = asyncio.create_task(wsclient('ws://localhost:8765/sonyCam'))
    task2 = asyncio.create_task(cameraLoop())

    taskCH = asyncio.create_task(cameraHold())
    await task1
    await task2
    await taskCH


if __name__ == "__main__":
    formatstr = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    # formatter = logging.Formatter(formatstr)
    logging.basicConfig(level=logging.INFO, format=formatstr)

    log = logging.getLogger(__name__)
    asyncio.run(main())


