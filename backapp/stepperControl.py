from typing import Tuple

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

def encodeLine(pname:str, value):
    # encode pname,value
    ba = pname.encode("ASCII")+bytearray(struct.pack("f", value))
    ba +="#".encode("ASCII")
    #b: bytes
    #hexmess = " ".join([hex(b) for b in bytearray(struct.pack("f", value))])
    #decmess = " ".join(["%d" % b for b in bytearray(struct.pack("f", value))])
#
    #logging.info(hexmess)
    logging.debug(ba)
    return ba

def decodeStepperLine(line:bytearray) -> str:
    """
    """
    linestr = line.decode("ascii").replace("\r\n","")
    return linestr

def sendParam(serialConnection:serial.Serial,ba):
    """
    send params to arduino
    """
    #  TODO try
    serialConnection.write(ba)
    serialConnection.flush()

    # TODO timeout
    line = serialConnection.readline()

    return decodeStepperLine(line)



MSGEARING=[
    [256, 0, 8000],
    [128, 4000, 16000],
    [64, 10000, 32000],
    [32, 21000, 64000],
    [16, 42000, 128000],
    [8, 85000, 256000],
    [4, 170000, 512000],
    [2, 340000, 1024000],
 ]

MSGEARINGDICT = {
    ms:[minx,maxx] for ms ,minx,maxx in MSGEARING
}

def getRangesForSpeed(speed):
    return [k for k,(minx,maxx) in MSGEARINGDICT.items() if abs(speed)<=maxx and abs(speed)>=minx]




class StepperMotor():

    def __init__(self,sa):
        self.log = logging.getLogger("stepper")
        self.sa:serial.Serial = sa
        self.maxSpeed= 8000
        self.currentTicking=0
        self.currentStepping = 256

        self.pinValue = 0
        self.autoConf()

    def autoConf(self):

        self.setTicking( 0)
        time.sleep(.2)

        self.setMicrosteps(256)
        time.sleep(.2)

        self.pinValue = self.getDiag()[0]


    def setSpeed(self,speed):
        #
        if self.currentStepping in getRangesForSpeed(speed):
            self.setTicking(speed/(256.0/self.currentStepping))

        else:
            newMS = max(getRangesForSpeed(speed))
            self.setMicrosteps(newMS)

            return self.setTicking(speed / (256.0 / newMS))


    def getDiag(self)->Tuple[int,int ]:
        """
        return pinValue,stepCount
        """
        line = sendParam(self.sa, encodeLine("D", 0))


        pinValue = 1 if "1" in line[0] else 0
        hexnum = line[1:-2]
        stepCount = int(hexnum)


        return pinValue,stepCount


    def setTicking(self, speed):
        self.currentTicking = speed
        return sendParam(self.sa, encodeLine("T", speed))

    def sendReset(self):
        return sendParam(self.sa, encodeLine("R", 0))

    def setMicrosteps(self,ms):
        self.currentStepping = ms
        return sendParam(self.sa, encodeLine("M", ms))

    def setCurrent(self,current):
        return sendParam(self.sa, encodeLine("I", current))



    def stopNow(self):
        
        return self.setTicking(0)


    def close(self):

        self.sa.close()
    def infoString(self):
        return "MS: %s, TC: %s"%(self.currentStepping,self.currentTicking)


def openTwoSerials(lineA,lineB):
    import serial
    log.info("opening StepperA")
    stepperA = StepperMotor(serial.Serial(lineA, 115200))

    log.info("opening StepperB")
    stepperB = StepperMotor(serial.Serial(lineB, 115200))

    if stepperA.pinValue == 1:
        stepperAsc = stepperA
        stepperDec = stepperB
    else:
        stepperAsc = stepperB
        stepperDec = stepperA

    return stepperAsc,stepperDec

def infiniteRetry(rerunTiming):
    def dec(f):
        async def wrap(*args,**kwargs):
            while True:
                try:
                    await f(*args,**kwargs)
                    await asyncio.sleep(rerunTiming)
                except Exception as e:
                    log.exception("infiniteRetry")
                    log.info("sleep for 5")
                    await asyncio.sleep(rerunTiming)

        return wrap
    return dec


stepperAsc:StepperMotor = None
stepperDec:StepperMotor = None
serialConnection = None
serverConnection = None

@infiniteRetry(rerunTiming=2)
async def bgjob():
    global serialConnection

    global serverConnection

    log = logging.getLogger("bgjob")

    log.info("serverConnection :%s",serverConnection)
    log.info("serialConnection :%s", serialConnection)

async def handle_ctlparams(data):

    global stepperAsc
    global stepperDec

    global serverConnection

    log = logging.getLogger("handle_ctlparams")
    log.info("setting speed %s",data)

    if data["k"] == "ASC" and stepperAsc is not None:
        res = stepperAsc.setSpeed(data["v"])
        log.info("setting ASC speed done: %s",res)
    if data["k"] == "DEC" and stepperDec is not None:
        res = stepperDec.setSpeed(data["v"])
        log.info("setting Dec speed done: %s",res)


    if data["k"] == "DEC_CURR" and stepperDec is not None:
        res = stepperDec.setCurrent(int(data["v"]))
        log.info("setting Dec current done: %s",res)
    if data["k"] == "ASC_CURR" and stepperAsc is not None:
        res = stepperAsc.setCurrent(int(data["v"]))
        log.info("setting ASC current done: %s",res)


    if data["k"] == "DEC_RESET" and stepperDec is not None:
        res = stepperDec.sendReset()
    if data["k"] == "ASC_RESET" and stepperAsc is not None:
        res = stepperAsc.sendReset()



@infiniteRetry(rerunTiming=2)
async def motorJob(uri):
    global serialConnection

    global serverConnection



    log = logging.getLogger("motorJob")


    try:
        log.info("connecting to %s", uri)
        async with websockets.connect(uri) as websocket:

            log = logging.getLogger("motorJob")
            log.info("Connected to server")
            serverConnection = websocket
            while True:
                data = await websocket.recv()

                msg = json.loads(data)
                log.info("got message %s", msg)
                msgType=msg["msgtype"]

                if msgType == "ctlparams":
                    await handle_ctlparams(msg)
                else:
                    log.info("got message %s", msg)


    except Exception as e:
        log.exception("wwop")
        serverConnection = None

    finally:
        serverConnection=None


@infiniteRetry(rerunTiming=15)
async def motorSerialJob():

    global stepperAsc
    global stepperDec

    log = logging.getLogger("motorSerialJob")
    import serial.tools.list_ports as port_list
    ports = list(port_list.comports())
    log.info("port list : %s",ports)
    stepperAsc, stepperDec = openTwoSerials("COM8", "COM3")

    stepperAsc.setCurrent(200)
    stepperDec.setCurrent(200)


    log.info("serialOpened")
    ascStepValue = 0;
    lastAscTime = 0;
    decStepValue = 0;

    while True:
        log.info("serial check")

        newascStep = stepperAsc.getDiag()[1]
        newascTime = time.time()


        ascSpeed = (newascStep-ascStepValue)/(newascTime-lastAscTime)

        log.info("ascSpeed = %.2f",ascSpeed)

        lastAscTime = newascTime
        ascStepValue = newascStep


        stepperDec.getDiag()[1]


        await asyncio.sleep(2)


async def main():

    task1 = asyncio.create_task( motorJob('ws://localhost:8765/motor'))

    task2 = asyncio.create_task( bgjob())
    task3 = asyncio.create_task(motorSerialJob())

    await task1
    await task2
    await task3


if __name__=="__main__":


    logging.basicConfig(level=logging.INFO)



    log = logging.getLogger(__name__)
    asyncio.run(main())

    """    stepperAsc,stepperDec = openTwoSerials("COM8", "COM3")

    stepperAsc.setCurrent(200)
    stepperDec.setCurrent(200)



    spd = 166*36

    print("speed %s" % spd)
    print(stepperAsc.infoString())

    stepperAsc.setSpeed(spd)
    stepperDec.setSpeed(spd)"""

    """spds = list(range(1, 12000, 1200))
    print(len(spds))


    for spd in spds:
        stepperAsc.setSpeed(spd)
        print("speed %s"%spd)
        print(stepperAsc.infoString())


        time.sleep(1)
"""


    #stepperAsc.stopNow()





