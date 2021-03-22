


import serial
import random
import logging
import asyncio
import websockets
import logging
import json
from collections import deque
import datetime
import time
import struct

serverConnection = None
serialConnection = None
readsBuff:list = []
BUFF_LIMIT = 50

def addReading(newVal):
    global readsBuff
    if len(readsBuff)>BUFF_LIMIT:
        readsBuff.pop(0)
    readsBuff.append(newVal)

def encodeLine(pname:str, value):
    # encode pname,value
    ba = pname.encode("ASCII")+bytearray(struct.pack("f", value))
    ba +="#".encode("ASCII")
    #b: bytes
    #hexmess = " ".join([hex(b) for b in bytearray(struct.pack("f", value))])
    #decmess = " ".join(["%d" % b for b in bytearray(struct.pack("f", value))])
#
    #logging.info(hexmess)
    #logging.info(decmess)
    return ba

def sendParam(serialConnection:serial.Serial,ba):
    """
    send params to arduino
    """
    serialConnection.write(ba)
    serialConnection.flush()


def decodeLine(line:bytearray):
    """
    """
    linestr = line.decode("ascii").replace("\r\n","")
    return {k:float(v) for k,v in [s.split(":") for s in linestr.split(" ")]}



def motorInfoMessage(info):
    return {
        "msgtype":"motorInfo",
        "data": info
    }

async def motorSerialJob(serialPort='/dev/ttyS0'):
    log = logging.getLogger("serialJob")

    while True:
        try:
            global serialConnection
            global serverConnection
            with serial.Serial(serialPort, 9600, timeout=1) as ser:

                #

                serialConnection = ser

                while True:
                    #x = ser.read()          # read one byte
                    #s = ser.read(10)        # read up to ten bytes (timeout)
                    line = ser.readline()   # read a '\n' terminated line

                    now = time.time()
                    try:
                        linedata = decodeLine(line)
                    except Exception as e:
                        log.warning("undecodable line %s %s", str(e), line)
                        linedata = None

                    if linedata is not None:
                        linedata["date"] = now
                        #log.info("got line from serial %s",linedata)

                        addReading(linedata)

                        if serverConnection is not None:
                            msg = motorInfoMessage(linedata)
                            await asyncio.wait([serverConnection.send(json.dumps(msg))])





                    await asyncio.sleep(.1)
            serialConnection = None

        except Exception as e:
            serialConnection = None
            log.warning(str(e))

        await asyncio.sleep(2)



async def motorJob(uri):
    log = logging.getLogger("motorJob")
    while True:
        try:
            log.info("connecting to %s",uri)
            async with websockets.connect(uri) as websocket:
                global serverConnection
                global serialConnection
                log=logging.getLogger("motorJob")
                log.info("Connected to server")
                serverConnection = websocket
                while True:
                    data = await websocket.recv()
                    log.info("got message %s",data)
                    msg=json.loads(data)

                    if msg["msgtype"] == "ctlparams":
                        # {"msgtype":"ctlparams","k":"T","v":3.0}
                        if serialConnection is not None:
                            sendParam(serialConnection,encodeLine(msg["k"],msg["v"]))
            serverConnection = None
        except Exception as e:
            serverConnection = None
            log.warning("websocket fail %s",str(e))

        await asyncio.sleep(2)

async def bgjob():
    log = logging.getLogger("bgjob")

    global serialConnection
    global readsBuff
    while True:
        log.info("bgjob")
        await asyncio.sleep(5)

        #if len(readsBuff)>0:
        #    import pandas as pd
        #    import matplotlib as plt
        #    df:pd.DataFrame = pd.DataFrame(readsBuff)
        #    errvar = df["err"].var()
        #    errmean = df["err"].mean()
        #    log.info("error stats  %.2f +/- %.5f",errmean,errvar)

        #    mspdvar = df["mspd"].var()
        #    mspdmean = df["mspd"].mean()
        #    log.info("speed stats  %.2f +/- %.5f", mspdmean, mspdvar)


async def main():


    serialPort= 'COM3'
    serialPort= '/dev/ttyACM0'


    task1 = asyncio.create_task( motorJob('ws://localhost:8765/motor'))

    task2 = asyncio.create_task( bgjob())
    task3 = asyncio.create_task(motorSerialJob(serialPort=serialPort))

    await task1
    await task2
    await task3


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import serial.tools.list_ports as port_list

    ports = list(port_list.comports())
    for p in ports:
        print(p)


    log = logging.getLogger(__name__)
    asyncio.run(main())

