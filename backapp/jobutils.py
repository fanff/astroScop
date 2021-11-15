import asyncio
import json
import logging

import websockets
from websockets import WebSocketClientProtocol


class Jobstate():
    def __init__(self):
        self.sc:WebSocketClientProtocol = None
    def __repr__(self):
        return "connected" if self.sc is not None else "not connected"
    def is_connected(self):
        return self.sc is not None
    async def send_msg(self,msgType,data):
        if self.is_connected():
            await self.sc.send(makeMessage(msgType, data, jdump=True))


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

async def clientConnection( uri,handle_ctlparams,state):
    """client connection"""
    log = logging.getLogger("clientconnection")
    log.info("connecting to %s", uri )
    try:
        async with websockets.connect(uri ) as websocket:
            log.info("Connected to server")
            state.sc=websocket
            while True:
                data = await websocket.recv()
                msg = json.loads(data)

                msgType = msg["msgtype"]

                await handle_ctlparams(msgType,msg,state)
    except Exception as e:
        state.sc = None
        raise
    state.sc = None


def infiniteRetry(rerunTiming):
    """
    retry decorator

    """
    def dec(f):
        async def wrap(*args, **kwargs):
            log=logging.getLogger("iRw")
            while True:
                try:
                    await f(*args, **kwargs)
                    await asyncio.sleep(rerunTiming)
                except Exception as e:
                    log.exception("infiniteRetry")
                    log.info("sleep for 5")
                    await asyncio.sleep(rerunTiming)

        return wrap

    return dec

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
