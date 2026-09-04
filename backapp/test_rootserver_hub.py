"""
Camera-free live tests for the rootserver hub.

Exercises typed params, JPEG passthrough + spectrum, overwhelm backpressure,
and params delivery under preview load. No picamera2 / hardware required.

Run from backapp/:
  python test_rootserver_hub.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
import time

import websockets

import rootserver
from cam_spectrum import SpectrumStats
from jobutils import MsgBuff
from ws_messages import (
    hist_data_from_spectrum,
    normalize_params_data,
    try_normalize_params,
)


def _tiny_jpeg_b64() -> str:
    # Minimal valid JPEG (1x1) base64
    raw = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\xff\xd9"
    )
    return base64.b64encode(raw).decode("utf-8")


def _fake_spectrum() -> dict:
    zeros = [0] * 256
    zeros[10] = 100
    return SpectrumStats(
        bins=256,
        mean_r=1.0,
        mean_g=2.0,
        mean_b=3.0,
        min_r=0,
        min_g=0,
        min_b=0,
        max_r=10,
        max_g=10,
        max_b=10,
        std_r=0.1,
        std_g=0.1,
        std_b=0.1,
        hist_r=list(zeros),
        hist_g=list(zeros),
        hist_b=list(zeros),
        pixels=1,
        shape=(1, 1, 3),
    ).model_dump()


async def _recv_until(ws, pred, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        msg = json.loads(raw)
        if pred(msg):
            return msg
    raise TimeoutError("condition not met before timeout")


async def _drain(ws, duration=0.05):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.01)
        except asyncio.TimeoutError:
            pass


async def with_hub(coro_fn):
    rootserver.reset_hub_state()
    # Avoid Windows path noise; still get ram+cpu
    server, port, tasks = await rootserver.start_hub(
        host="127.0.0.1", port=0, disklist=[]
    )
    try:
        await coro_fn(port)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        server.close()
        await server.wait_closed()
        rootserver.reset_hub_state()


def test_msgbuff_drop_flag():
    buf = MsgBuff(1)
    assert buf.stack("a") is False
    assert buf.stack("b") is True
    assert list(buf.content) == ["b"]
    assert len(buf) == 1


def test_normalize_strips_iso():
    s = normalize_params_data(
        {"shutterSpeed": 1000, "isovalue": 800, "analog_gain": 2.5, "redgain": 1.1}
    )
    d = s.to_wire_dict()
    assert d["shutter_us"] == 1000
    assert d["analog_gain"] == 2.5
    assert d["colour_gain_r"] == 1.1
    assert "isovalue" not in d
    assert try_normalize_params({"analog_gain": -1}) is None


def test_preview_div_and_wh():
    from cam_settings import CameraSettings, from_legacy_dict, preview_wh_from_frame

    assert preview_wh_from_frame((666, 494), 1) == (666, 494)
    assert preview_wh_from_frame((666, 494), 2) == (332, 246)
    assert preview_wh_from_frame((666, 494), 8) == (82, 60)
    # odd inputs forced even after divide
    assert preview_wh_from_frame((2028, 1520), 2) == (1014, 760)

    s = from_legacy_dict({"preview_div": 4}, {})
    assert s.preview_div == 4
    # legacy absolute display size ignored → default 2
    s2 = from_legacy_dict({"display_width": 320, "display_height": 240}, {})
    assert s2.preview_div == 2
    assert "display_width" not in s2.to_wire_dict()
    assert CameraSettings().preview_div == 2


def test_hist_from_spectrum():
    spec = _fake_spectrum()
    hist = hist_data_from_spectrum(spec)
    assert len(hist) == 3
    assert len(hist[0]) == 256
    assert hist[0][10] > 0


async def test_params_canonical_and_legacy(port: int):
    cam_msgs = []

    async def camera():
        async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as ws:
            while True:
                raw = await ws.recv()
                cam_msgs.append(json.loads(raw))

    cam_task = asyncio.create_task(camera())
    await asyncio.sleep(0.05)

    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ui:
        # Legacy
        await ui.send(
            json.dumps(
                {
                    "msgtype": "params",
                    "data": {
                        "shutterSpeed": 50000,
                        "isovalue": 400,
                        "analog_gain": 1.5,
                        "redgain": 1.0,
                        "bluegain": 1.2,
                    },
                }
            )
        )
        await asyncio.sleep(0.1)
        assert cam_msgs, "camera should receive params"
        last = cam_msgs[-1]
        assert last["msgtype"] == "params"
        assert last["data"]["shutter_us"] == 50000
        assert last["data"]["analog_gain"] == 1.5
        assert "isovalue" not in last["data"]

        # Canonical
        await ui.send(
            json.dumps(
                {
                    "msgtype": "params",
                    "data": {
                        "sensor_preset": "bin2x2",
                        "shutter_us": 12000,
                        "analog_gain": 3.0,
                        "max_emit_fps": 5.0,
                    },
                }
            )
        )
        await asyncio.sleep(0.1)
        last = cam_msgs[-1]
        assert last["data"]["shutter_us"] == 12000
        assert last["data"]["analog_gain"] == 3.0
        assert last["data"]["max_emit_fps"] == 5.0

        await ui.send(
            json.dumps(
                {
                    "msgtype": "params",
                    "data": {
                        "locator_enabled": True,
                        "locator_x": 0.25,
                        "locator_y": 0.75,
                    },
                }
            )
        )
        await asyncio.sleep(0.1)
        last = cam_msgs[-1]
        assert last["data"]["locator_enabled"] is True
        assert abs(float(last["data"]["locator_x"]) - 0.25) < 1e-9
        assert abs(float(last["data"]["locator_y"]) - 0.75) < 1e-9

        # Invalid — not forwarded
        n = len(cam_msgs)
        await ui.send(json.dumps({"msgtype": "params", "data": {"analog_gain": -5}}))
        await asyncio.sleep(0.1)
        assert len(cam_msgs) == n

    cam_task.cancel()
    try:
        await cam_task
    except asyncio.CancelledError:
        pass


async def test_srcimage_passthrough_spectrum(port: int):
    jpeg = _tiny_jpeg_b64()
    spectrum = _fake_spectrum()
    used = {"shutter_us": 1000, "analog_gain": 2.0, "settings": {"shutter_us": 1000}}

    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ui:
        async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as cam:
            await cam.send(
                json.dumps(
                    {
                        "msgtype": "srcimage",
                        "imageData": jpeg,
                        "usedParams": used,
                        "spectrum": spectrum,
                    }
                )
            )
            img = await _recv_until(ui, lambda m: m.get("msgtype") == "imgData")
            assert img["data"] == jpeg
            props = await _recv_until(ui, lambda m: m.get("msgtype") == "imgProps")
            assert props["data"]["usedParams"]["shutter_us"] == 1000
            stats = await _recv_until(ui, lambda m: m.get("msgtype") == "imgStats")
            assert "spectrum" in stats["data"]
            assert stats["data"]["spectrum"]["bins"] == 256
            assert "histData" in stats["data"]
            assert len(stats["data"]["histData"]) == 3


async def test_overwhelm_edge(port: int):
    jpeg = _tiny_jpeg_b64()
    overwhelm_msgs = []

    async def camera():
        async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as ws:
            # Pause consumer by not yielding to hub forwarder? We flood from cam.
            for i in range(20):
                await ws.send(
                    json.dumps(
                        {
                            "msgtype": "srcimage",
                            "imageData": jpeg + ("x" * (i % 3)),  # unique payloads
                            "usedParams": {"i": i},
                        }
                    )
                )
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("msgtype") == "serverOverwhelmed":
                    overwhelm_msgs.append(msg["data"])
                    if msg["data"] is False and True in overwhelm_msgs:
                        return

    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ui:
        # Drain UI so forwarder can clear the queue
        drain = asyncio.create_task(_drain(ui, duration=2.0))
        await camera()
        await drain

    assert True in overwhelm_msgs, "expected serverOverwhelmed true"
    assert False in overwhelm_msgs, "expected serverOverwhelmed false after drain"
    # Edge: first transition to true before any false
    assert overwhelm_msgs[0] is True


async def test_params_rtt_under_load(port: int):
    jpeg = ("A" * 50_000)  # large fake base64 payload
    got = asyncio.Event()
    rtt = {}

    async def camera():
        async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as ws:
            flood = True

            async def flooder():
                i = 0
                while flood:
                    await ws.send(
                        json.dumps(
                            {
                                "msgtype": "srcimage",
                                "imageData": jpeg,
                                "usedParams": {"i": i},
                            }
                        )
                    )
                    i += 1
                    await asyncio.sleep(0)

            t = asyncio.create_task(flooder())
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("msgtype") == "params" and msg.get("data", {}).get("shutter_us") == 4242:
                    rtt["end"] = time.monotonic()
                    got.set()
                    flood = False
                    t.cancel()
                    return
                if msg.get("msgtype") == "serverOverwhelmed":
                    continue

    cam_task = asyncio.create_task(camera())
    await asyncio.sleep(0.05)

    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ui:
        drain = asyncio.create_task(_drain(ui, duration=3.0))
        await asyncio.sleep(0.05)
        rtt["start"] = time.monotonic()
        await ui.send(
            json.dumps(
                {
                    "msgtype": "params",
                    "data": {"shutter_us": 4242, "analog_gain": 1.0},
                }
            )
        )
        await asyncio.wait_for(got.wait(), timeout=2.0)
        await drain

    cam_task.cancel()
    try:
        await cam_task
    except asyncio.CancelledError:
        pass

    elapsed_ms = (rtt["end"] - rtt["start"]) * 1000
    assert elapsed_ms < 500, f"params RTT under load too slow: {elapsed_ms:.1f} ms"


async def test_sysinfo_ram_cpu(port: int):
    async with websockets.connect(f"ws://127.0.0.1:{port}/stats") as ws:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        assert msg["msgtype"] == "sysInfo"
        disks = {d["disk"] for d in msg["data"]}
        assert "ram" in disks
        assert "cpu" in disks


async def test_cam_reconnect_resends_params(port: int):
    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ui:
        await ui.send(
            json.dumps(
                {
                    "msgtype": "params",
                    "data": {"shutter_us": 7777, "analog_gain": 1.0},
                }
            )
        )
        await asyncio.sleep(0.05)

    async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as cam:
        msg = json.loads(await asyncio.wait_for(cam.recv(), timeout=2.0))
        assert msg["msgtype"] == "params"
        assert msg["data"]["shutter_us"] == 7777


async def test_srcimage_seeds_current_params(port: int):
    """First srcimage with usedParams.settings seeds hub when currentParams is None."""
    jpeg = _tiny_jpeg_b64()
    used = {
        "shutter_us": 4242,
        "analog_gain": 2.25,
        "settings": {
            "shutter_us": 4242,
            "analog_gain": 2.25,
            "sensor_preset": "bin2x2",
            "include_raw": True,
            "science_neutral": True,
            "colour_gain_r": 3.5,
            "colour_gain_b": 1.5,
            "preview_div": 2,
            "save_enabled": False,
            "save_format": "none",
            "save_section": "test",
            "save_subsection": "",
            "save_root": "./savedimgs",
            "max_emit_fps": 8.0,
        },
    }

    async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as cam:
        await cam.send(
            json.dumps(
                {
                    "msgtype": "srcimage",
                    "imageData": jpeg,
                    "usedParams": used,
                }
            )
        )
        await asyncio.sleep(0.1)

    async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as cam2:
        msg = json.loads(await asyncio.wait_for(cam2.recv(), timeout=2.0))
        assert msg["msgtype"] == "params"
        assert msg["data"]["shutter_us"] == 4242
        assert abs(float(msg["data"]["analog_gain"]) - 2.25) < 1e-6

    # A later frame must not overwrite UI-set currentParams.
    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ui:
        await ui.send(
            json.dumps(
                {
                    "msgtype": "params",
                    "data": {"shutter_us": 9999, "analog_gain": 1.0},
                }
            )
        )
        await asyncio.sleep(0.05)

    async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as cam3:
        # Drain the reconnect resend first
        msg = json.loads(await asyncio.wait_for(cam3.recv(), timeout=2.0))
        assert msg["msgtype"] == "params"
        assert msg["data"]["shutter_us"] == 9999
        await cam3.send(
            json.dumps(
                {
                    "msgtype": "srcimage",
                    "imageData": jpeg,
                    "usedParams": used,
                }
            )
        )
        await asyncio.sleep(0.1)

    async with websockets.connect(f"ws://127.0.0.1:{port}/camera") as cam4:
        msg = json.loads(await asyncio.wait_for(cam4.recv(), timeout=2.0))
        assert msg["msgtype"] == "params"
        assert msg["data"]["shutter_us"] == 9999


async def run_all():
    logging.basicConfig(level=logging.WARNING)
    test_msgbuff_drop_flag()
    test_normalize_strips_iso()
    test_preview_div_and_wh()
    test_hist_from_spectrum()
    print("unit ok")

    await with_hub(test_params_canonical_and_legacy)
    print("params ok")
    await with_hub(test_srcimage_passthrough_spectrum)
    print("srcimage ok")
    await with_hub(test_overwhelm_edge)
    print("overwhelm ok")
    await with_hub(test_params_rtt_under_load)
    print("rtt ok")
    await with_hub(test_sysinfo_ram_cpu)
    print("sysinfo ok")
    await with_hub(test_cam_reconnect_resends_params)
    print("reconnect ok")
    await with_hub(test_srcimage_seeds_current_params)
    print("seed currentParams ok")
    print("ALL PASS")


if __name__ == "__main__":
    # Ensure backapp is on path when run as script
    sys.path.insert(0, ".")
    try:
        asyncio.run(run_all())
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
    except Exception as e:
        logging.exception("test error")
        print("FAIL:", e)
        sys.exit(1)
