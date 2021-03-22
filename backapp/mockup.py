import asyncio
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

DEBUGMODE = 0


currentImage = None
currentUsedParams = None

currentParams = None


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


WSCAMERA = None
WSMOTOR = None
USERS = set()


async def register(websocket):
    USERS.add(websocket)


async def unregister(websocket):
    USERS.remove(websocket)



async def sendImage(imgData):
    log = logging.getLogger("sendImage")
    if len(USERS)>0:

        strSend = time.time()
        message = json.dumps({"type": "imgData", "data": imgData})
        log.info("sending message size %s to %s users", len(message),len(USERS))
        await asyncio.wait([user.send(message) for user in USERS])
        endSend = time.time()
        log.info("sendImage %s", endSend - strSend)


async def sendImageProps(imgProps):
    if USERS:
        log = logging.getLogger("sendImageProps")

        strSend = time.time()
        message = json.dumps({"type": "imgProps", "data": imgProps})
        await asyncio.wait([user.send(message) for user in USERS])
        endSend = time.time()
        log.info("sendDur: %s", endSend - strSend)


async def sendImageStats(imgStats):
    if USERS:
        log = logging.getLogger("sendImageStats")

        strSend = time.time()
        message = json.dumps({"type": "imgStats", "data": imgStats})
        await asyncio.wait([user.send(message) for user in USERS])
        endSend = time.time()
        log.debug("sendDur: %s", endSend - strSend)



async def bcastMsg(data, msgtype):
    if USERS:
        message = json.dumps({"type": msgtype, "data": data})
        await asyncio.wait([user.send(message) for user in USERS])


async def bcastImg(currentImage, usedParams):
    b64imgData = imgutils.pilimTobase64Jpg(currentImage)
    histData = imgutils.colorHist(currentImage)

    await sendImage(b64imgData)

    imgProps = {"usedParams": usedParams,
                "triggerDate": "no info",
                }
    await sendImageProps(imgProps)

    imgStats = {"histData": histData, }
    await sendImageStats(imgStats)
    await asyncio.sleep(.4)


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
                        await WSCAMERA.send(msg)
                    else:
                        log.info("setting new params, no camera detected")
                elif msg["msgtype"] == "ctlparams":
                    await WSMOTOR.send(rawData)

                elif msg["msgtype"] == "srcimage":
                    log.info("got image")
                    decoded = base64.b64decode(msg["imageData"].encode("utf-8"))
                    currentImage = Image.open(io.BytesIO(decoded))
                    currentUsedParams = msg["usedParams"]
                    await bcastImg(currentImage, currentUsedParams)
                elif msg["msgtype"] == "motorInfo":
                    log.info("got motor info data ")
                    await bcastMsg(msg["data"], "motorInfo")

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
        else:
            await unregister(websocket)


async def bgjob():
    log = logging.getLogger("bgjob")
    global currentParams
    sleepdur = 1
    while True:

        if DEBUGMODE:
            log.info("current parameters %s", currentParams)

            usedParams = copy.deepcopy(currentParams)

            triggerDate = time.time()
            tosleep = float(usedParams["shutterSpeed"]) / (10e6)
            await asyncio.sleep(tosleep)
            shootresol = usedParams["shootresol"]
            imgData, histData = makeRandomImage(shootresol["width"], shootresol["height"])

            b64imgData = base64.b64encode(imgData).decode("utf-8")
            log.info("img data %s %s", len(imgData), len(b64imgData))

            imgProps = {"usedParams": usedParams,
                        "triggerDate": triggerDate,
                        }
            await sendImage(b64imgData)
            await sendImageProps(imgProps)

            imgStats = {"histData": histData, }
            await sendImageStats(imgStats)
        else:

            total, used, free = [float(_) / (2 ** 30) for _ in shutil.disk_usage("/")]
            log.info("disk info %s %s %s", total, used, free)
            await bcastMsg({"total": total, "used": used, "free": free}, "sysInfo")
            await asyncio.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    WSHOST = "0.0.0.0"
    WSPORT = 8765

    logging.info("listening at ws://%s:%s"%(WSHOST, WSPORT))
    start_server = websockets.serve(handler, WSHOST, WSPORT)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_until_complete(bgjob())
    asyncio.get_event_loop().run_forever()
