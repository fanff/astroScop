import asyncio
import os

import websockets
import time
import numpy as np
import logging
import json
from pprint import pprint

from PIL import Image,ImageDraw
import numpy as np

import psutil
import io
import base64
import copy

import shutil

import imgutils
# from backapp import imgutils
from jobutils import MsgBuff, makeMessage, infiniteRetry

DEBUGMODE = 0
currentImage = None
currentUsedParams = None

currentParams = None

WSCAMERA = None
WSMOTOR = None
USERS = set()

SONYCAMERA = None
latestgyroData = None


MOTORSTATS=MsgBuff(1000)
CAMSTATS=MsgBuff(1000)
IMGSFORWEB=MsgBuff(1)

overWhelmed = False

def makeRandomImage(width, height):
    # random Pil Image
    arr = np.random.randint(0, 255, (width, height, 3))
    im = Image.fromarray(arr, 'RGB')

    # calc hist
    histData = imgutils.colorHist2(im)

    # convert Pil to JPG data
    b = io.BytesIO()

    im.save(b, format="JPEG")

    data = b.getvalue()

    return data, histData



async def overwhelmedStart():
    global overWhelmed

    global WSCAMERA

    overWhelmed = True
    if WSCAMERA:
        await WSCAMERA.send(makeMessage("serverOverwhelmed",True,jdump=True))

async def overwhelmedEnd():
    global overWhelmed

    global WSCAMERA

    overWhelmed = False
    if WSCAMERA:
        await WSCAMERA.send(makeMessage("serverOverwhelmed",False,jdump=True))







async def register(websocket):
    USERS.add(websocket)
async def unregister(websocket):
    USERS.remove(websocket)



async def bcastMsg(data, msgtype):
    """
    broadcast to all web users 
    """
    log = logging.getLogger("bcastcastMsg")
    if len(USERS)>0:
        strSend = time.time()
        message = makeMessage(msgtype,data,jdump=True)
        log.debug("broadcasting message size %s to %s users", len(message),len(USERS))
        await asyncio.wait([user.send(message) for user in USERS])

        endSend = time.time()
        log.debug("sendDur: %s", endSend - strSend)

async def bcastImg(currentImage, usedParams):
    b64imgData = imgutils.pilimTobase64Jpg(currentImage)
    histData = imgutils.colorHist2(currentImage)

    await bcastMsg(b64imgData, "imgData")
    imgProps = {"usedParams": usedParams,
                "triggerDate": "no info",
                }
    await bcastMsg(imgProps, "imgProps")

    imgStats = {"histData": histData, }
    await bcastMsg(imgStats, "imgStats")

class SonyCamera(object):


    def __init__(self,websocket,path):
        self.websocket = websocket
        self.path = path
        self.log = logging.getLogger("SonyCam")

    async def handeSonyCamera(self):

        while True:
            rawData = await self.websocket.recv()
            self.log.debug("got message")

            try:
                msg = json.loads(rawData)
                if msg["msgtype"] in ["sonySequenceInfo","sonyCurrentConfig"]:
                    self.log.info("broadcasting info to clients %s",msg["msgtype"])
                    await bcastMsg(msg["data"], msg["msgtype"])
            except Exception as e:
                self.log.exception("wtf")


    async def send(self,rawdata):
        res = await self.websocket.send(rawdata)

        self.log.info("sent some data %s",res)
        return


async def handler(websocket, path):
    global currentParams
    global currentImage
    global currentUsedParams
    global WSCAMERA
    global WSMOTOR
    global SONYCAMERA
    log = logging.getLogger("handler")
    log.info("client Connected on path %s", path)

    if "camera" in path:
        WSCAMERA = websocket
        if currentParams:
            await WSCAMERA.send(json.dumps({"msgtype":"params","data":currentParams}))
    elif "motor" in path:

        log.info("setting motor connection")
        WSMOTOR = websocket

    elif "sonyCam" in path:

        log.info("sony Camera Connected !")

        SONYCAMERA = SonyCamera(websocket,path)
        await SONYCAMERA.handeSonyCamera()

    elif "stats" in path:
        log.info("pushing stats")
        try:
            data = scanDiskUsage(DISKLIST)
            await websocket.send(makeMessage("sysInfo",data,jdump=True))

            await websocket.send(makeMessage("motorstats", MOTORSTATS.content, jdump=True))
            await websocket.send(makeMessage("camstats", CAMSTATS.content,  jdump=True))

        except Exception as e:
            log.info("error with stats")
        return
    elif "gyro" in path:
        pass

    else:
        # register as a new user
        await register(websocket)



    try:
        while True:
            rawData = await websocket.recv()
            try:
                msg = json.loads(rawData)
                if msg["msgtype"] == "params":
                    currentParams = msg["data"]
                    if WSCAMERA:
                        log.info("sending params to camera")

                        try:
                            await WSCAMERA.send(rawData)
                        except Exception as e:
                            log.warning("could not send data to WS CAMERA")

                    else:
                        log.info("setting new params but no camera detected")
                elif msg["msgtype"] == "ctlparams":
                    # 
                    log.info("ctlParams %s",msg)
                    if WSMOTOR is not None:
                        await WSMOTOR.send(rawData)
                    else:
                        log.info("setting new params but no motor detected")

                elif msg["msgtype"] == "srcimage":

                    IMGSFORWEB.stack(msg)
                    if len(IMGSFORWEB.content) >=2:
                        await overwhelmedStart()
                        log.info("start overWhelmed")


                elif msg["msgtype"] == "motorInfo":

                    MOTORSTATS.stack(msg["data"])
                    await bcastMsg(msg["data"], "motorInfo")

                elif msg["msgtype"] == "camTiming":
                    # relay camera timing to users
                    CAMSTATS.stack(msg["data"])
                    await bcastMsg(msg["data"], "camTiming")


                elif msg["msgtype"] in ["sonyparams","sonyShoot"]:
                    log.info("pushing to camera %s",SONYCAMERA)
                    if SONYCAMERA is not None:
                        await SONYCAMERA.send(rawData)

                elif msg["msgtype"] in ["gyrodata"]:
                    log.info("got gyro data %s", msg)
                    global latestgyroData
                    latestgyroData = msg
                else:
                    log.info("message type %s ?",msg["msgtype"])

            except Exception as e:
                log.exception("bad message! %s", e)
                log.warning("bad message!")
    except websockets.exceptions.ConnectionClosed as e:
        log.info("client disconnected")
    except websockets.exceptions.ConnectionClosedOK as e:
        log.info("client disconnected")
    except Exception as e:
        log.error("error type %s", type(e))
        log.exception("error")
    finally:
        if "camera" in path:
            log.warning("camera closed connection :(")
            WSCAMERA = None
        elif "motor" in path:
            log.warning("motor connection close")
            WSMOTOR = None
        else:
            await unregister(websocket)



def drawCircle(img_draw,w,h,pixRadius,width=2,outline = "#0F0F"): 
    img_draw.ellipse((w-pixRadius,h-pixRadius, w+pixRadius,h+pixRadius), fill = None, outline =outline,width=2)

@infiniteRetry(.02)
async def forwardImageToWeb():
    log = logging.getLogger("fwdImage")
    global currentParams
    global WSMOTOR
    global WSCAMERA
    global USERS

    inbuff= len(IMGSFORWEB.content)
    if inbuff >0:
        msg = IMGSFORWEB.pop()
        strt = time.time()
        decoded = base64.b64decode(msg["imageData"].encode("utf-8"))
        currentImage = Image.open(io.BytesIO(decoded))
        currentUsedParams = msg["usedParams"]

        # draw overlay

        log.debug("drawing overlay on image with params %s",currentUsedParams)
        img_draw = ImageDraw.Draw(currentImage)

        cameraWFov = float(currentUsedParams.get("cameraWfov",22.5))

        relw = .5+currentUsedParams.get("markXloc",.0)/2.0
        relh = .5 +currentUsedParams.get("markYloc",.0)/2.0

        crosscenter  = currentImage.size[0]*relw , currentImage.size[1]*relh


        degByPix = cameraWFov/currentImage.size[0]


        pixRadius = 1.0/degByPix
        if pixRadius <1.0:
            pixRadius = 1.0
        log.debug("with w:%.2f,h:%.2f,  pix:%.1f",relw,relh,pixRadius)
        drawCircle(img_draw,crosscenter[0],crosscenter[1],pixRadius=int(pixRadius),width=2,outline = "#F0F")
        drawCircle(img_draw,crosscenter[0],crosscenter[1],pixRadius=int(pixRadius*2),width=2,outline = "#F0F")
        drawCircle(img_draw,crosscenter[0],crosscenter[1],pixRadius=int(pixRadius*5),width=2,outline = "#F0F")

        if latestgyroData is not None:
            pitch = latestgyroData["data"]["pitch"]
            rot = 90.0-latestgyroData["data"]["roll"]
            log.info("rotation by %.2f", rot)
            currentImage = currentImage.rotate(rot, center=crosscenter, fillcolor="black")

            img_draw = ImageDraw.Draw(currentImage)

            pixByDeg = currentImage.size[1]/cameraWFov
            for pitchline_angle in range(-90,90,5):
                if abs( pitch-pitchline_angle) < 20:
                    diffpix = (pitchline_angle-pitch)*pixByDeg

                    drawCircle(img_draw, crosscenter[0], crosscenter[1]+diffpix, pixRadius=2, width=2,
                               outline="#F0F")

                    img_draw.text(xy=(crosscenter[0], crosscenter[1]+diffpix),
                             text= "%s"%pitchline_angle,
                             fill="#F0F")

                    img_draw.line(xy=[(crosscenter[0]-50, crosscenter[1]+diffpix),
                                      (crosscenter[0]+50, crosscenter[1]+diffpix)
                                      ],fill="#F0F", width=2)


        log.debug("image decodeTo Image dur %.2f",time.time()-strt)
        try:
            await bcastImg(currentImage, currentUsedParams)
        except Exception as e:
            log.exception("error broadcasting image")

        dur = time.time()-strt
        log.info("sending to all clients dur %.2f",dur)

        await asyncio.sleep(.05)
        if len(IMGSFORWEB.content)<inbuff:
            await overwhelmedEnd()


async def bgjob(diskList):
    log = logging.getLogger("bgjob")
    global currentParams
    global WSMOTOR
    global WSCAMERA
    global USERS
    sleepdur = 5
    while True:
        try:
            data= scanDiskUsage(diskList)
            await bcastMsg(data,"sysInfo")

            #MOTORSTATS.saveAsJson("./motorstats.json")
            #CAMSTATS.saveAsJson("./camStats.json")

            servst =serviceStatus()

            log.info("serviceStatus is %s", servst)
            await asyncio.sleep(sleepdur)
        except Exception as e:
            log.exception("error")
            await asyncio.sleep(sleepdur)

def serviceStatus():
    global WSMOTOR
    global WSCAMERA
    global USERS
    serviceStatus = {}
    for subserv, ws in zip(["WSMOTOR", "WSCAMERA"], [WSMOTOR, WSCAMERA]):
        status = "OK" if (ws is not None) else "NOT CONNECTED"

        serviceStatus[subserv] = [status, 0]

    serviceStatus["WEBUSERS"] = ["OK", len(USERS)]
    serviceStatus["OVERWHELM"] = ["OK", str(overWhelmed)]

    return serviceStatus



def scanDiskUsage(diskList):
    log = logging.getLogger("diskinfo")
    # scan disk usage

    res = []
    for diskIdent in diskList :
        if os.path.exists(diskIdent):
            total, used, free = [float(_) / (2 ** 30) for _ in shutil.disk_usage(diskIdent)]
            usedpct = (used/total)*100
            log.info("in %s using %.1f %% of %.1f Go ; %.1f Go free", diskIdent , usedpct , total,free)
            res.append({
                "total": total, "used": used, "usedpct": usedpct,
                "free": free, "disk": diskIdent})

    # adding memory usage ?a
    import psutil
    mem = psutil.virtual_memory()
    
    giga = float(1024**3)
    res.append({
                "total": mem.total/giga, "used": mem.used/giga, "usedpct": mem.percent,
                "free": mem.available/giga, "disk": "ram"})


    return res


async def runWebSock():

    async with websockets.serve(handler, WSHOST, WSPORT) as srv:
        pass

def main():

    WSHOST = "0.0.0.0"
    WSPORT = 8765
    
    DISKLIST = ["/","/dev/shm"]
    
    logging.info("listening at ws://%s:%s"%(WSHOST, WSPORT))
    
    srvobject = websockets.serve(handler, WSHOST, WSPORT)
    asyncio.get_event_loop().run_until_complete(srvobject) 

    asyncio.get_event_loop().create_task(forwardImageToWeb())




    asyncio.get_event_loop().create_task(bgjob(DISKLIST))

    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    loggingLevel = logging.INFO # 20; ERROR is 40 
    logging.basicConfig(level=loggingLevel)
    main()
    #asyncio.run(main())


