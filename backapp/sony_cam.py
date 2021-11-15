


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
from jobutils import formatstr, parse_args
from rootserver import makeMessage, MsgBuff
import datetime
from subprocess import call,run
import shutil
import sonyConfigUtils

def findMagicExtension(baseshm):
    return [f.split(".")[1] for f in os.listdir(baseshm) if "capt000" in f][0]



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

currentAction = None
IMGBUFF = MsgBuff(2)

async def camerahandler(my_cam):
    global sequence
    global currentAction
    global IMGBUFF


    log = logging.getLogger("cameraHandler")


    while True:

        if len(sequence)>0:
            act,params = sequence.pop()
            currentAction = act,params
            log.info("action is %s",act)
            #help(my_cam)

            if act == "listConfig":
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await asyncio.get_running_loop().run_in_executor(
                            pool, lambda :run(["gphoto2","--list-all-config"],capture_output=True)  )
                try:
                    lines = result.stdout.decode("utf-8").split("\n")

                    log.info("lines %s",lines) 
                    sections = sonyConfigUtils.linesToSection(lines)
                    sonyConfig = sorted([sonyConfigUtils.secToDict(sec) for sec in sections],key= lambda x:["key"])


                    # got confgig!!
                    if serverConnection: 
                        await serverConnection.send(
                            makeMessage("sonyCurrentConfig", sonyConfig, jdump=True))

                    log.info("got config !")
                except Exception as e:
                    log.exception("error capture file %s",e)
                currentAction = None 

            elif act == "capture_cli":


                baseshm = "/dev/shm/buff/"
                destshm = "./savedimgs/sony/"
                #imgSaver = imgutils.ImgSaver("./savedimgs/")
                os.makedirs(baseshm,exist_ok=True)
                os.makedirs(destshm,exist_ok=True)

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = await asyncio.get_running_loop().run_in_executor(
                            pool, lambda :call(["gphoto2","--capture-image-and-download"],cwd=baseshm)  )

                try:
                    extension = findMagicExtension(baseshm)
                    imageFileName = "img_%d.%s"%(time.time(),extension)

                    cstfilename = "capt0000.%s"%extension
                    
                    finalName = os.path.join(destshm,imageFileName)
                    shutil.move(os.path.join(baseshm,cstfilename),finalName)
                    
                    log.info("file in %s",finalName)
                except Exception as e:
                    log.error("error capture file %s",e)
                
                if params is not None:
                    if params > 0:
                        sequence.push(("capture_cli" ,params-1))
                currentAction=None

            elif act == "set_param":
                try:
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

                except Exception as e:
                    log.error("error setting parameter %s",e)
                
                await asyncio.sleep(1)
                sequence.push(("listConfig" ,None))
                await asyncio.sleep(1)
                sequence.push(("listConfig" ,None))
                currentAction=None


        else:
            await asyncio.sleep(.5)



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
                    log.info("got a message")

                    if msg["msgtype"] == "addInSeq":
                        sequence.push(("capture_cli",None))
                    elif msg["msgtype"] == "sonyparams":
                        pdict = msg["data"]
                        for k,v in pdict.items():

                            log.info("pushing into sequennce configuration %s:%s",k,v)
                            sequence.push(("set_param",{"key":k,"index":v}))
                    elif msg["msgtype"] == "sonyShoot":
                        pdict = msg["data"]
                        

                        sequence.push(("capture_cli",int(pdict["countPict"])))

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
    global sequence
    global currentAction
    log = logging.getLogger("camloop")
    while True:
        # monitor sequence size
        # current action
        # if preview_image available, push it to serv

        if len(IMGBUFF.content)>0:
            # pop

            if serverConnection and not serverOverwhelmed:
                await serverConnection.send(
                    makeMessage("previewImage", None, jdump=True))
        
        if serverConnection:
            seqinfo ={"sequence":sequence.seq,"currentAction":currentAction}
            log.info("pushing sequence Info %s",seqinfo)
            await serverConnection.send( 
                            makeMessage("sonySequenceInfo", seqinfo, jdump=True) )
        else:
            log.info("no server")
        await asyncio.sleep(1)


async def main(args):
    uri = 'ws://localhost:8765/sonyCam' if args.uri is None else args.uri

    task1 = asyncio.create_task(wsclient(uri))
    task2 = asyncio.create_task(cameraLoop())

    taskCH = asyncio.create_task(cameraHold())
    await task1
    await task2
    await taskCH


if __name__ == "__main__":
    args = parse_args()
    # formatter = logging.Formatter(formatstr)
    logging.basicConfig(level=logging.INFO, format=formatstr)

    log = logging.getLogger(__name__)
    asyncio.run(main())


