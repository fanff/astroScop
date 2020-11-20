


import serial

import logging
import asyncio
import websockets
import logging



serverConnection = None


async def motorJob():
    log = logging.getLogger("motorJob")
    
    try:
        with serial.Serial('/dev/ttyS0', 9600, timeout=1) as ser:
            x = ser.read()          # read one byte
            s = ser.read(10)        # read up to ten bytes (timeout)
            line = ser.readline()   # read a '\n' terminated line

            print(line)
    except Exception as e:
        log.exception("wooops")
async def motorJob(uri):


    async with websockets.connect(uri) as websocket:
        global serverConnection 
        log=logging.getLogger("motorJob")
        log.info("Connected to server")
        serverConnection = websocket
        while True:
            data = await websocket.recv()
            #log.info("got message %s",data)
            freshParams=json.loads(data)
            

async def bgjob():
    log = logging.getLogger("bgjob")
    sleepdur = 1
    while True:
        log.info("bgjob")
        await asyncio.sleep(sleepdur)

async def main():
    task1 = asyncio.create_task( hello('ws://localhost:8765/camera'))
    task2 = asyncio.create_task( bgjob())
    
    await task1
    await task2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)
    asyncio.run(main())

