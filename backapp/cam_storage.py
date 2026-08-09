"""
Bayer science storage in a separate OS process (avoids GIL contention).

Camera process copies uint16 Bayer into a shared_memory ring and sends a
small job message (slot id + metadata + runtime path). The storage process
writes ``*_bayer.npy`` + ``*_meta.json`` only — never RGB/JPEG.
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import time
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger("cam_storage")

CMD_SHUTDOWN = "shutdown"
CMD_FRAME = "frame"
CMD_STATS = "stats"


def _dest_dir(save_root: str, section: str, subsection: str) -> str:
    if subsection:
        return os.path.join(save_root, section, subsection)
    return os.path.join(save_root, section)


def write_bayer_frame(
    array_u16: np.ndarray,
    meta: Dict[str, Any],
    save_root: str,
    save_section: str,
    save_subsection: str,
    sequence: int,
) -> Tuple[str, str]:
    """Write Bayer .npy + JSON sidecar. Returns (npy_path, meta_path)."""
    dest = _dest_dir(save_root, save_section, save_subsection)
    os.makedirs(dest, exist_ok=True)
    stem = f"frame_{sequence:06d}"
    npy_path = os.path.join(dest, f"{stem}_bayer.npy")
    meta_path = os.path.join(dest, f"{stem}_meta.json")
    np.save(npy_path, array_u16)
    payload = dict(meta)
    payload["sequence"] = sequence
    payload["science_path"] = npy_path
    payload["array_shape"] = list(array_u16.shape)
    payload["dtype"] = str(array_u16.dtype)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return npy_path, meta_path


def storage_process_main(
    job_queue: mp.Queue,
    free_queue: mp.Queue,
    stats_queue: mp.Queue,
    shm_names: List[str],
    slot_nbytes: int,
) -> None:
    """Child process entry: drain Bayer jobs from shared memory to disk."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    slog = logging.getLogger("cam_storage.worker")
    try:
        os.nice(10)
    except Exception:
        pass

    shms: List[shared_memory.SharedMemory] = []
    try:
        for name in shm_names:
            shms.append(shared_memory.SharedMemory(name=name))
    except Exception:
        slog.exception("failed attaching shared memory")
        return

    written = 0
    errors = 0
    slog.info("storage process ready slots=%s nbytes=%s", len(shms), slot_nbytes)

    try:
        while True:
            try:
                msg = job_queue.get()
            except (EOFError, OSError):
                break
            if msg is None:
                continue
            mtype = msg.get("type")
            if mtype == CMD_SHUTDOWN:
                slog.info("shutdown written=%s errors=%s", written, errors)
                break
            if mtype == CMD_STATS:
                try:
                    stats_queue.put(
                        {"written": written, "errors": errors},
                        block=False,
                    )
                except Exception:
                    pass
                continue
            if mtype != CMD_FRAME:
                slog.warning("unknown job type %s", mtype)
                continue

            slot = int(msg["slot"])
            shape = tuple(msg["shape"])
            dtype = np.dtype(msg["dtype"])
            nbytes = int(np.prod(shape) * dtype.itemsize)
            if nbytes > slot_nbytes:
                slog.error("frame nbytes %s > slot %s", nbytes, slot_nbytes)
                errors += 1
                free_queue.put(slot)
                continue

            try:
                buf = np.ndarray(shape, dtype=dtype, buffer=shms[slot].buf)
                # Copy out of shm before returning the slot so parent can reuse.
                arr = np.array(buf, copy=True)
                write_bayer_frame(
                    arr,
                    msg.get("meta") or {},
                    msg["save_root"],
                    msg.get("save_section") or "test",
                    msg.get("save_subsection") or "",
                    int(msg["sequence"]),
                )
                written += 1
            except Exception:
                slog.exception("failed writing sequence=%s", msg.get("sequence"))
                errors += 1
            finally:
                free_queue.put(slot)
    finally:
        for shm in shms:
            try:
                shm.close()
            except Exception:
                pass


@dataclass
class StorageStats:
    published: int = 0
    dropped: int = 0
    written: int = 0
    errors: int = 0


class ScienceStorageClient:
    """
    Parent-side client: owns shm ring + child Process.

    ``publish`` never waits on disk — if no free slot, the frame is dropped.
    """

    def __init__(self, n_slots: int = 16):
        self.n_slots = int(n_slots)
        self._ctx = mp.get_context("spawn")
        self._job_q: Optional[mp.Queue] = None
        self._free_q: Optional[mp.Queue] = None
        self._stats_q: Optional[mp.Queue] = None
        self._proc: Optional[mp.Process] = None
        self._shms: List[shared_memory.SharedMemory] = []
        self._slot_nbytes = 0
        self._seq = 0
        self.stats = StorageStats()
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def start(self, slot_nbytes: int) -> None:
        """Create ring + start storage process. Idempotent if already running same size."""
        slot_nbytes = int(slot_nbytes)
        if slot_nbytes < 64:
            raise ValueError("slot_nbytes too small")
        if self._proc is not None and self._proc.is_alive() and slot_nbytes == self._slot_nbytes:
            return
        self.shutdown()
        self._slot_nbytes = slot_nbytes
        self._job_q = self._ctx.Queue()
        self._free_q = self._ctx.Queue()
        self._stats_q = self._ctx.Queue()
        names: List[str] = []
        for i in range(self.n_slots):
            shm = shared_memory.SharedMemory(create=True, size=slot_nbytes)
            self._shms.append(shm)
            names.append(shm.name)
            self._free_q.put(i)
        self._proc = self._ctx.Process(
            target=storage_process_main,
            args=(self._job_q, self._free_q, self._stats_q, names, slot_nbytes),
            name="cam-bayer-storage",
            daemon=True,
        )
        self._proc.start()
        log.info(
            "storage process started pid=%s slots=%s nbytes=%s",
            self._proc.pid,
            self.n_slots,
            slot_nbytes,
        )

    def ensure_capacity(self, shape: Tuple[int, ...], dtype=np.uint16) -> None:
        """Ensure ring slots fit an array of the given shape."""
        need = int(np.prod(shape) * np.dtype(dtype).itemsize)
        # Pad a little for stride variance (e.g. 4064 vs 4056).
        need = max(need, need + 4096)
        if self._proc is None or not self._proc.is_alive() or need > self._slot_nbytes:
            self.start(need)

    def publish(
        self,
        array_u16: np.ndarray,
        meta: Dict[str, Any],
        save_root: str,
        save_section: str = "test",
        save_subsection: str = "",
    ) -> bool:
        """
        Copy Bayer into a free shm slot and enqueue a write job.

        Returns False if disabled or no free slot (frame dropped).
        """
        if not self._enabled:
            return False
        if self._proc is None or not self._proc.is_alive():
            log.warning("storage process not running; drop frame")
            self.stats.dropped += 1
            return False

        arr = np.ascontiguousarray(array_u16)
        if arr.dtype != np.uint16:
            arr = arr.astype(np.uint16, copy=False)
        nbytes = int(arr.nbytes)
        if nbytes > self._slot_nbytes:
            log.warning("bayer nbytes %s > slot %s; dropping", nbytes, self._slot_nbytes)
            self.stats.dropped += 1
            return False

        try:
            slot = self._free_q.get_nowait()
        except Exception:
            self.stats.dropped += 1
            return False

        try:
            dest = np.ndarray(arr.shape, dtype=arr.dtype, buffer=self._shms[slot].buf)
            np.copyto(dest, arr)
            self._seq += 1
            job = {
                "type": CMD_FRAME,
                "slot": int(slot),
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "nbytes": nbytes,
                "sequence": self._seq,
                "save_root": str(save_root),
                "save_section": str(save_section or "test"),
                "save_subsection": str(save_subsection or ""),
                "meta": meta,
            }
            self._job_q.put(job)
            self.stats.published += 1
            return True
        except Exception:
            log.exception("publish failed")
            self.stats.dropped += 1
            try:
                self._free_q.put(slot)
            except Exception:
                pass
            return False

    def poll_stats(self) -> StorageStats:
        """Non-blocking pull of child written/error counters."""
        if self._stats_q is None or self._job_q is None:
            return self.stats
        try:
            self._job_q.put({"type": CMD_STATS}, block=False)
        except Exception:
            pass
        try:
            while True:
                msg = self._stats_q.get_nowait()
                self.stats.written = int(msg.get("written", self.stats.written))
                self.stats.errors = int(msg.get("errors", self.stats.errors))
        except Exception:
            pass
        return self.stats

    def shutdown(self, timeout: float = 2.0) -> None:
        proc = self._proc
        job_q = self._job_q
        self._proc = None
        if proc is not None and proc.is_alive() and job_q is not None:
            try:
                job_q.put({"type": CMD_SHUTDOWN})
            except Exception:
                pass
            proc.join(timeout=timeout)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1.0)
        for shm in self._shms:
            try:
                shm.close()
                shm.unlink()
            except Exception:
                pass
        self._shms = []
        self._job_q = None
        self._free_q = None
        self._stats_q = None
        self._slot_nbytes = 0
