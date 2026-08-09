"""
WebSocket hub: UI ↔ rootserver ↔ camera / motor.

Camera params are validated with CameraSettings before forward.
Preview frames are passthrough (no JPEG decode/overlay on the event loop).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time

import psutil
import websockets

from jobutils import MsgBuff, makeMessage, infiniteRetry
from ws_messages import (
    hist_data_from_spectrum,
    parse_cam_timing,
    parse_srcimage,
    try_normalize_params,
)

DEBUGMODE = 0
currentImage = None
currentUsedParams = None

currentParams = None  # canonical CameraSettings.to_wire_dict() or None

WSCAMERA = None
WSMOTOR = None
USERS = set()

latestgyroData = None

MOTORSTATS = MsgBuff(1000)
CAMSTATS = MsgBuff(1000)
IMGSFORWEB = MsgBuff(1)

overWhelmed = False

DISKLIST = ["/", "/dev/shm"]


def reset_hub_state():
    """Clear module globals (tests)."""
    global currentImage, currentUsedParams, currentParams
    global WSCAMERA, WSMOTOR, latestgyroData, overWhelmed
    currentImage = None
    currentUsedParams = None
    currentParams = None
    WSCAMERA = None
    WSMOTOR = None
    latestgyroData = None
    overWhelmed = False
    USERS.clear()
    MOTORSTATS.content.clear()
    CAMSTATS.content.clear()
    IMGSFORWEB.content.clear()


async def overwhelmedStart():
    """Edge-triggered: notify camera that the hub dropped a preview frame."""
    global overWhelmed
    global WSCAMERA

    if overWhelmed:
        return
    overWhelmed = True
    if WSCAMERA:
        await WSCAMERA.send(makeMessage("serverOverwhelmed", True, jdump=True))


async def overwhelmedEnd():
    """Edge-triggered: hub queue drained; camera may emit again."""
    global overWhelmed
    global WSCAMERA

    if not overWhelmed:
        return
    overWhelmed = False
    if WSCAMERA:
        await WSCAMERA.send(makeMessage("serverOverwhelmed", False, jdump=True))


async def register(websocket):
    USERS.add(websocket)


async def unregister(websocket):
    USERS.discard(websocket)


async def bcastMsg(data, msgtype):
    """Broadcast to all web users."""
    log = logging.getLogger("bcastcastMsg")
    if len(USERS) > 0:
        strSend = time.time()
        message = makeMessage(msgtype, data, jdump=True)
        log.debug("broadcasting message size %s to %s users", len(message), len(USERS))
        await asyncio.gather(
            *[user.send(message) for user in USERS],
            return_exceptions=True,
        )
        log.debug("sendDur: %s", time.time() - strSend)


async def bcastPassthroughFrame(image_data: str, used_params, spectrum=None):
    """
    Forward camera JPEG + metadata without re-encoding.

    UI msgtypes kept for compatibility: imgData / imgProps / imgStats.
    """
    global currentUsedParams
    currentUsedParams = used_params

    await bcastMsg(image_data, "imgData")
    await bcastMsg(
        {"usedParams": used_params, "triggerDate": "no info"},
        "imgProps",
    )
    img_stats = {}
    if spectrum is not None:
        try:
            img_stats["histData"] = hist_data_from_spectrum(spectrum)
            img_stats["spectrum"] = (
                spectrum.model_dump() if hasattr(spectrum, "model_dump") else spectrum
            )
        except Exception:
            logging.getLogger("bcastFrame").exception("spectrum → histData failed")
    await bcastMsg(img_stats, "imgStats")


async def handler(websocket, path=None):
    global currentParams
    global WSCAMERA
    global WSMOTOR
    global latestgyroData
    log = logging.getLogger("handler")
    # websockets>=13: path is on websocket.request; older APIs passed path as arg
    if path is None:
        path = getattr(getattr(websocket, "request", None), "path", "") or ""
    log.info("client Connected on path %s", path)

    if "camera" in path:
        WSCAMERA = websocket
        if currentParams:
            await WSCAMERA.send(params_to_wire_from_dict(currentParams))
    elif "motor" in path:
        log.info("setting motor connection")
        WSMOTOR = websocket
    elif "stats" in path:
        log.info("pushing stats")
        try:
            data = scanDiskUsage(DISKLIST)
            await websocket.send(makeMessage("sysInfo", data, jdump=True))
            await websocket.send(makeMessage("motorstats", MOTORSTATS.content, jdump=True))
            await websocket.send(makeMessage("camstats", CAMSTATS.content, jdump=True))
        except Exception:
            log.info("error with stats")
        return
    elif "gyro" in path:
        pass
    else:
        await register(websocket)

    try:
        while True:
            rawData = await websocket.recv()
            try:
                msg = json.loads(rawData)
                msgtype = msg.get("msgtype")

                if msgtype == "params":
                    settings = try_normalize_params(msg.get("data"))
                    if settings is None:
                        continue
                    currentParams = settings.to_wire_dict()
                    wire = params_to_wire_from_dict(currentParams)
                    if WSCAMERA:
                        log.info("sending validated params to camera")
                        try:
                            await WSCAMERA.send(wire)
                        except Exception:
                            log.warning("could not send data to WS CAMERA")
                    else:
                        log.info("setting new params but no camera detected")

                elif msgtype == "ctlparams":
                    log.info("ctlParams %s", msg)
                    if WSMOTOR is not None:
                        await WSMOTOR.send(rawData)
                    else:
                        log.info("setting new params but no motor detected")

                elif msgtype == "srcimage":
                    try:
                        frame = parse_srcimage(msg)
                    except Exception:
                        log.exception("invalid srcimage")
                        continue
                    dropped = IMGSFORWEB.stack(frame)
                    if dropped:
                        await overwhelmedStart()
                        log.info("start overWhelmed (preview drop)")

                elif msgtype == "motorInfo":
                    MOTORSTATS.stack(msg["data"])
                    await bcastMsg(msg["data"], "motorInfo")

                elif msgtype == "camTiming":
                    try:
                        timing = parse_cam_timing(msg)
                        payload = timing.data.model_dump()
                    except Exception:
                        payload = msg.get("data", msg)
                    CAMSTATS.stack(payload)
                    await bcastMsg(payload, "camTiming")

                elif msgtype in ["gyrodata"]:
                    log.info("got gyro data %s", msg)
                    latestgyroData = msg
                else:
                    log.info("message type %s ?", msgtype)

            except Exception as e:
                log.exception("bad message! %s", e)
                log.warning("bad message!")
    except websockets.exceptions.ConnectionClosed:
        log.info("client disconnected")
    except websockets.exceptions.ConnectionClosedOK:
        log.info("client disconnected")
    except Exception as e:
        log.error("error type %s", type(e))
        log.exception("error")
    finally:
        if "camera" in path:
            log.warning("camera closed connection :(")
            WSCAMERA = None
        elif "motor" in path:
            log.warning("motor connection close")
            WSMOTOR = None
        elif "stats" not in path:
            await unregister(websocket)


def params_to_wire_from_dict(data: dict) -> str:
    return json.dumps({"msgtype": "params", "data": data})


@infiniteRetry(0.01)
async def forwardImageToWeb():
    """Pop queued frames and passthrough-broadcast; clear overwhelm when empty."""
    log = logging.getLogger("fwdImage")

    if len(IMGSFORWEB) == 0:
        return

    frame = IMGSFORWEB.pop()
    strt = time.time()
    try:
        spectrum = frame.spectrum
        await bcastPassthroughFrame(frame.imageData, frame.usedParams, spectrum)
    except Exception:
        log.exception("error broadcasting image")

    dur = time.time() - strt
    log.debug("passthrough to clients dur %.4f", dur)

    if len(IMGSFORWEB) == 0:
        await overwhelmedEnd()


async def bgjob(diskList):
    log = logging.getLogger("bgjob")
    sleepdur = 5
    while True:
        try:
            data = scanDiskUsage(diskList)
            await bcastMsg(data, "sysInfo")
            servst = serviceStatus()
            log.info("serviceStatus is %s", servst)
            await asyncio.sleep(sleepdur)
        except Exception:
            log.exception("error")
            await asyncio.sleep(sleepdur)


def serviceStatus():
    global WSMOTOR
    global WSCAMERA
    global USERS
    status = {}
    for subserv, ws in zip(["WSMOTOR", "WSCAMERA"], [WSMOTOR, WSCAMERA]):
        status[subserv] = ["OK" if (ws is not None) else "NOT CONNECTED", 0]
    status["WEBUSERS"] = ["OK", len(USERS)]
    status["OVERWHELM"] = ["OK", str(overWhelmed)]
    return status


def scanDiskUsage(diskList):
    log = logging.getLogger("diskinfo")
    res = []
    for diskIdent in diskList:
        if os.path.exists(diskIdent):
            total, used, free = [float(_) / (2 ** 30) for _ in shutil.disk_usage(diskIdent)]
            usedpct = (used / total) * 100 if total else 0.0
            log.info(
                "in %s using %.1f %% of %.1f Go ; %.1f Go free",
                diskIdent,
                usedpct,
                total,
                free,
            )
            res.append(
                {
                    "total": total,
                    "used": used,
                    "usedpct": usedpct,
                    "free": free,
                    "disk": diskIdent,
                }
            )

    mem = psutil.virtual_memory()
    giga = float(1024 ** 3)
    res.append(
        {
            "total": mem.total / giga,
            "used": mem.used / giga,
            "usedpct": mem.percent,
            "free": mem.available / giga,
            "disk": "ram",
        }
    )

    # Non-blocking sample (first call after process start may be 0.0).
    cpu_pct = float(psutil.cpu_percent(interval=None))
    res.append(
        {
            "total": 100.0,
            "used": cpu_pct,
            "usedpct": cpu_pct,
            "free": max(0.0, 100.0 - cpu_pct),
            "disk": "cpu",
        }
    )
    return res


async def start_hub(host="127.0.0.1", port=0, disklist=None):
    """
    Start the hub server. Returns (server, port, tasks).

    ``port=0`` binds an ephemeral port (useful for tests).
    Caller should cancel ``tasks`` when shutting down.
    """
    if disklist is None:
        disklist = list(DISKLIST)

    server = await websockets.serve(
        handler, host, port, max_size=32 * 1024 * 1024
    )
    bound = server.sockets[0].getsockname()[1]
    logging.info("listening at ws://%s:%s", host, bound)
    tasks = [
        asyncio.create_task(forwardImageToWeb()),
        asyncio.create_task(bgjob(disklist)),
    ]
    return server, bound, tasks


async def amain():
    host = "0.0.0.0"
    port = 8765
    logging.info("listening at ws://%s:%s", host, port)
    async with websockets.serve(
        handler, host, port, max_size=32 * 1024 * 1024
    ):
        asyncio.create_task(forwardImageToWeb())
        asyncio.create_task(bgjob(DISKLIST))
        await asyncio.Future()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
