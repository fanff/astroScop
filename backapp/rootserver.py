import asyncio
import os

import websockets
import time
import numpy as np
import logging
import json
from pprint import pprint

from PIL import Image
import numpy as np

import io
import base64
import copy

import shutil

import imgutils
# from backapp import imgutils


class MsgBuff():
    def __init__(self,maxcount):
        self.maxcount = maxcount
        self.content= []
    def stack(self,data):
        while len(self.content)>=self.maxcount:
            self.content = self.content[1:]
        self.content.append(data)


    def pop(self):
        poped = self.content[0]
        self.content = self.content[1:]
        return poped
    def saveAsJson(self,jsonName):
        with open(jsonName,"w") as fou:
            json.dump(self.content,fou)


DEBUGMODE = 0
currentImage = None
currentUsedParams = None

currentParams = None

WSCAMERA = None
WSMOTOR = None
USERS = set()


MOTORSTATS=MsgBuff(1000)
CAMSTATS=MsgBuff(1000)

def makeRandomImage(width, height):
    # random Pil Image
    arr = np.random.randint(0, 255, (width, height, 3))
    im = Image.fromarray(arr, 'RGB')

    # calc hist
    histData = imgutils.colorHist(im)

    # convert Pil to JPG data
    b = io.BytesIO()

    im.save(b, format="JPEG")

    data = b.getvalue()

    return data, histData





def makeMessage(msgtype,data,jdump=False):
    """
    {"msttype": "string",
    "data": }
    """
    msg ={"msgtype": msgtype, "data": data}
    if jdump:
        return json.dumps(msg)
    else:
        return msg




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
    histData = imgutils.colorHist(currentImage)

    await bcastMsg(b64imgData, "imgData")
    imgProps = {"usedParams": usedParams,
                "triggerDate": "no info",
                }
    await bcastMsg(imgProps, "imgProps")

    imgStats = {"histData": histData, }
    await bcastMsg(imgStats, "imgStats")


async def handler(websocket, path):
    global currentParams
    global currentImage
    global currentUsedParams
    global WSCAMERA
    global WSMOTOR
    log = logging.getLogger("handler")
    log.info("client Connected on path %s", path)

    if "camera" in path:
        WSCAMERA = websocket
        if currentParams:
            await WSCAMERA.send(json.dumps({"msgtype":"params","data":currentParams}))
    elif "motor" in path:

        log.info("setting motor connection")
        WSMOTOR = websocket

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
                        await WSCAMERA.send(rawData)
                    else:
                        log.info("setting new params but no camera detected")
                elif msg["msgtype"] == "ctlparams":
                    # 
                    if WSMOTOR is not None:
                        await WSMOTOR.send(rawData)
                    else:
                        log.info("setting new params but no motor detected")

                elif msg["msgtype"] == "srcimage":

                    strt = time.time()
                    decoded = base64.b64decode(msg["imageData"].encode("utf-8"))
                    currentImage = Image.open(io.BytesIO(decoded))
                    currentUsedParams = msg["usedParams"]
                    # TODO keep usedParams in a stack 

                    log.info("image decodeTo Image dur %.2f",time.time()-strt)
                    strt = time.time()
                    await bcastImg(currentImage, currentUsedParams)
                    log.info("sending to all clients dur %.2f",time.time()-strt)


                elif msg["msgtype"] == "motorInfo":
                    MOTORSTATS.stack(msg["data"])
                    await bcastMsg(msg["data"], "motorInfo")

                elif msg["msgtype"] == "camTiming":
                    # relay camera timing to users
                    CAMSTATS.stack(msg["data"])
                    await bcastMsg(msg["data"], "camTiming")
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
            log.warning("no camera around :(")
            WSCAMERA = None
        elif "motor" in path:
            log.warning("motor connection close")
            WSMOTOR = None
        else:
            await unregister(websocket)





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


    return res


if __name__ == "__main__":

    WSHOST = "0.0.0.0"
    WSPORT = 8765
    
    DISKLIST = ["/","/dev/shm"]
    
    loggingLevel = logging.INFO # 20; ERROR is 40 
    
    logging.basicConfig(level=loggingLevel)
    logging.info("listening at ws://%s:%s"%(WSHOST, WSPORT))
    start_server = websockets.serve(handler, WSHOST, WSPORT)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_until_complete(bgjob(DISKLIST))
    asyncio.get_event_loop().run_forever()
