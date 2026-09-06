"""Lock-centered native RGB crop + latest-wins shm handoff (Phase D).

Camera copies a small tile; isolation / PID / JPEG stay out of this module.
"""

from __future__ import annotations

import struct
import time
import uuid
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Optional, Sequence

import numpy as np

from guide_roi import lock_to_roi

SLOT_NAME = "astroscop-guide-tile"
MAX_SIDE = 128
HEADER_SIZE = 64
PAYLOAD_SIZE = MAX_SIDE * MAX_SIDE * 3
SLOT_SIZE = HEADER_SIZE + PAYLOAD_SIZE
# magic, seq, t_ns, origin_u, origin_v, size_u, size_v, lock_u, lock_v, ok, pad
_HDR = struct.Struct("<4sQQiiHHddB15x")
_MAGIC = b"GDT1"
assert _HDR.size == HEADER_SIZE


@dataclass
class GuideTile:
    rgb: np.ndarray
    origin_u: int
    origin_v: int
    lock_u: float
    lock_v: float
    t: float


def extract_guide_tile(
    rgb: np.ndarray,
    track_x: float,
    track_y: float,
    *,
    scaler_crop: Optional[Sequence] = None,
    roi_half: int = 32,
    t: Optional[float] = None,
) -> Optional[GuideTile]:
    """Copy a lock-centered square from capture RGB. None if the lock is unusable."""
    if rgb is None or getattr(rgb, "ndim", 0) != 3:
        return None
    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    roi = lock_to_roi(
        track_x,
        track_y,
        (w, h),
        scaler_crop=scaler_crop,
        roi_half=roi_half,
        center_uv=None,
    )
    if not roi.ok:
        return None
    v0, v1 = roi.origin_v, roi.origin_v + roi.size_v
    u0, u1 = roi.origin_u, roi.origin_u + roi.size_u
    tile = np.ascontiguousarray(rgb[v0:v1, u0:u1])
    if tile.shape[0] > MAX_SIDE or tile.shape[1] > MAX_SIDE:
        return None
    return GuideTile(
        rgb=tile,
        origin_u=roi.origin_u,
        origin_v=roi.origin_v,
        lock_u=roi.lock_u,
        lock_v=roi.lock_v,
        t=time.time() if t is None else float(t),
    )


class GuideTileSlot:
    """Single named shm slot. Camera writes; guide reads the latest seq."""

    def __init__(self, shm: shared_memory.SharedMemory, *, owner: bool) -> None:
        self.shm = shm
        self.owner = owner
        self._seq = 0

    @classmethod
    def create(cls, name: str = SLOT_NAME) -> "GuideTileSlot":
        try:
            shm = shared_memory.SharedMemory(name=name, create=True, size=SLOT_SIZE)
        except FileExistsError:
            stale = shared_memory.SharedMemory(name=name)
            stale.close()
            stale.unlink()
            shm = shared_memory.SharedMemory(name=name, create=True, size=SLOT_SIZE)
        slot = cls(shm, owner=True)
        slot.shm.buf[:HEADER_SIZE] = b"\x00" * HEADER_SIZE
        return slot

    @classmethod
    def attach(cls, name: str = SLOT_NAME) -> "GuideTileSlot":
        shm = shared_memory.SharedMemory(name=name, create=False)
        return cls(shm, owner=False)

    def close(self, unlink: Optional[bool] = None) -> None:
        do_unlink = self.owner if unlink is None else bool(unlink)
        try:
            self.shm.close()
        except Exception:
            pass
        if do_unlink:
            try:
                self.shm.unlink()
            except Exception:
                pass

    def write(self, tile: GuideTile) -> None:
        rgb = np.ascontiguousarray(tile.rgb)
        h, w = int(rgb.shape[0]), int(rgb.shape[1])
        if h > MAX_SIDE or w > MAX_SIDE:
            raise ValueError("tile larger than GuideTileSlot max side")
        view = np.ndarray((h, w, 3), dtype=np.uint8, buffer=self.shm.buf, offset=HEADER_SIZE)
        view[:] = rgb
        self._seq += 1
        hdr = _HDR.pack(
            _MAGIC,
            self._seq,
            int(float(tile.t) * 1e9),
            int(tile.origin_u),
            int(tile.origin_v),
            w,
            h,
            float(tile.lock_u),
            float(tile.lock_v),
            1,
        )
        self.shm.buf[:HEADER_SIZE] = hdr

    def read(self) -> Optional[GuideTile]:
        raw = bytes(self.shm.buf[:HEADER_SIZE])
        unpacked = _HDR.unpack(raw)
        magic, seq, t_ns, ou, ov, w, h, lu, lv, ok = unpacked[:10]
        if magic != _MAGIC or not seq or not ok:
            return None
        w, h = int(w), int(h)
        if w < 1 or h < 1 or w > MAX_SIDE or h > MAX_SIDE:
            return None
        view = np.ndarray((h, w, 3), dtype=np.uint8, buffer=self.shm.buf, offset=HEADER_SIZE)
        rgb = np.ascontiguousarray(view)
        seq2 = _HDR.unpack(bytes(self.shm.buf[:HEADER_SIZE]))[1]
        if seq2 != seq:
            return None
        return GuideTile(
            rgb=rgb,
            origin_u=int(ou),
            origin_v=int(ov),
            lock_u=float(lu),
            lock_v=float(lv),
            t=float(t_ns) / 1e9,
        )


class GuidePublisher:
    """Lazy slot owned by the camera process. No-op when tracking is off."""

    def __init__(self, name: str = SLOT_NAME) -> None:
        self.name = name
        self._slot: Optional[GuideTileSlot] = None

    def on_frame(
        self,
        rgb: np.ndarray,
        *,
        track_enabled: bool,
        track_x: float,
        track_y: float,
        track_roi: int,
        scaler_crop: Optional[Sequence] = None,
        t: Optional[float] = None,
    ) -> Optional[GuideTile]:
        if not track_enabled:
            # Keep the named slot. Unlinking here orphans the guide worker's
            # attach (same name, new inode) until that process restarts.
            return None
        tile = extract_guide_tile(
            rgb,
            track_x,
            track_y,
            scaler_crop=scaler_crop,
            roi_half=track_roi,
            t=t,
        )
        if tile is None:
            return None
        if self._slot is None:
            self._slot = GuideTileSlot.create(self.name)
        self._slot.write(tile)
        return tile

    def close(self) -> None:
        if self._slot is not None:
            self._slot.close(unlink=True)
            self._slot = None


def unique_slot_name() -> str:
    return f"astroscop-guide-tile-{uuid.uuid4().hex[:12]}"
