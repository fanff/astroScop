


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





def cameraAct(func):
    logth = logging.getLogger("cameraAct")
    try:
        return func()
    except Exception as e:
        logth.exception("wwww")
        return None

sequence = []
IMGBUFF = MsgBuff(2)


async def camerahandler(my_cam):
    global sequence
    global IMGBUFF


    log = logging.getLogger("cameraHandler")

    while True:

        if len(sequence)>0:
            act = next(sequence)

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
                        pool, cameraAct,lambda : my_cam.capture() )

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
            import gphoto2cffi as gp

            # List all attached cameras that are supported
            cams = gp.list_cameras()
            for cam in cams:
                log.info(cam)

            # Get a camera instance by specifying a USB bus and device number
            bus = 4
            device = 1

            log.info("connecting to bus=%s ,  device=%s",bus, device)
            my_cam = gp.Camera(bus=bus, device=device)
            log.info(my_cam)
            # Get an instance for the first supported camera
            #my_cam = gp.Camera()
            # or
            #my_cam = next(gp.list_cameras())



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


