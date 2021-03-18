


import serial

import logging
import asyncio
import websockets
import logging
import json


import struct

serverConnection = None
serialConnection = None


def encodeLine(pname:str, value):
    # encode pname,value
    ba = pname.encode("ASCII")+bytearray(struct.pack("f", value))
    ba +="#".encode("ASCII")
    return ba

def sendParam(serialConnection:serial.Serial,ba):
    serialConnection.write(ba)
    serialConnection.flush()


def decodeLine(line:bytearray):
    """
    """
    linestr = line.decode("ascii").replace("\r\n","")
    return {k:float(v) for k,v in [s.split(":") for s in linestr.split(" ")]}


async def motorSerialJob(serialPort='/dev/ttyS0'):
    log = logging.getLogger("serialJob")
    try:
        global serialConnection
        with serial.Serial(serialPort, 9600, timeout=1) as ser:

            #

            serialConnection = ser

            while True:
                #x = ser.read()          # read one byte
                #s = ser.read(10)        # read up to ten bytes (timeout)
                line = ser.readline()   # read a '\n' terminated line

                try:
                    linedata = decodeLine(line)
                    log.info("got line from serial %s",linedata)
                except Exception as e :
                    log.warning("undecodable line %s %s",str(e) ,line)


                await asyncio.sleep(.1)
        serialConnection = None

    except Exception as e:
        serialConnection = None
        log.exception("wooops")



async def motorJob(uri):
    log = logging.getLogger("motorJob")
    try:
        async with websockets.connect(uri) as websocket:
            global serverConnection
            global serialConnection
            log=logging.getLogger("motorJob")
            log.info("Connected to server")
            serverConnection = websocket
            while True:
                data = await websocket.recv()
                log.info("got message %s",data)
                freshParams=json.loads(data)
                if serialConnection is not None:
                    sendParam(serialConnection,encodeLine("P",11.2))
        serverConnection = None
    except Exception as e:
        serverConnection = None
        log.exception("wooops")

async def bgjob():
    log = logging.getLogger("bgjob")
    sleepdur = 1
    while True:
        log.info("bgjob")
        await asyncio.sleep(sleepdur)

async def main():


    serialPort= 'COM3'


    task1 = asyncio.create_task( motorJob('ws://localhost:8765/camera'))

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

