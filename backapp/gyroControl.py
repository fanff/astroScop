import asyncio
import json
import logging
import time

import numpy as np
import websockets
from websockets import WebSocketClientProtocol

from jobutils import clientConnection, Jobstate, parse_args
from stepperControl import infiniteRetry


def cart2sph(c):
    x,y,z = c
    XsqPlusYsq = x**2 + y**2
    r = np.sqrt(XsqPlusYsq + z**2)               # r
    elev = np.arctan2(z,np.sqrt(XsqPlusYsq))     # theta
    az = np.arctan2(y,x)                           # phi
    return np.array([r, elev, az])




async def handle_ctlparams(msgType,msg,state):
    log = logging.getLogger("handle_ctlparams")


    if msgType == "sysInfo":
        log.info("%s : %s",msgType,msg)
    else:
        log.info("cccc %s", msgType)


@infiniteRetry(rerunTiming=2)
async def gyroJob(uri,state):
    await clientConnection(uri, handle_ctlparams,state)

@infiniteRetry(rerunTiming=2)
async def bgjob(state:Jobstate):

    logging.info("state %s",state)

    import adafruit_mpu6050
    import board

    i2c = board.I2C()  # uses board.SCL and board.SDA
    mpu = adafruit_mpu6050.MPU6050(i2c)
    gyro = np.array([0,0,1])
    while True:

        ac = mpu.acceleration
        x,y,z = -ac[1],ac[0],  ac[2]

        gyronew = np.array([x,y,z])

        damping = .9
        gyro = (gyronew * (1.0-damping)) + (gyro * damping)

        x,y,z = gyro
        # print("Temperature: %.2f C"%mpu.temperature)
        elev, az = np.rad2deg(cart2sph(gyro)[1:])
        # elev = 90-elev


        roll = np.arctan2(y, z) * 57.3
        pitch = np.arctan2((- x), np.sqrt(y**2 + z**2)) * 57.3

        data = {"elev":elev,"az":az,
                "roll": roll, "pitch": pitch,}



        logging.info("%s",data)
        await state.send_msg("gyrodata",data)
        await asyncio.sleep(.1)






async def main(args):
    uri = 'ws://localhost:8765/gyro' if args.uri is None else args.uri
    state = Jobstate()
    task1 = asyncio.create_task(gyroJob(uri,state))
    task2 = asyncio.create_task(bgjob(state))
    #task3 = asyncio.create_task(motorSerialJob())

    await task1
    await task2
    #await task3



if __name__ == "__main__":
    args = parse_args()


    logging.basicConfig(level=logging.INFO)

    log = logging.getLogger(__name__)
    asyncio.run(main(args))