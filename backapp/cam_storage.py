"""
Bayer science storage in a separate OS process (avoids GIL contention).

Camera process copies uint16 Bayer into a single shared_memory slab (ring of
slots) and sends a small job message (slot id + metadata + runtime path).
The storage process writes ``*_bayer.npy`` + ``*_meta.json`` only — never RGB/JPEG.

One contiguous shm segment keeps the FD count at ~1 regardless of slot count
(per-slot shm previously exhausted ulimit at 512 slots).
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import time
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any, Dict, Optional, Tuple

import numpy as np

log = logging.getLogger("cam_storage")

CMD_SHUTDOWN = "shutdown"
CMD_FRAME = "frame"
CMD_STATS = "stats"

# Worst-case IMX477 Bayer planning size (~30 MiB) — used only for docs / fallback.
MAX_BAYER_SLOT_MIB = 30
DEFAULT_RAM_FRACTION = 0.60
MIN_RING_SLOTS = 16
MAX_RING_SLOTS = 512
# Leave headroom on tmpfs for mp queues / other users.
DEFAULT_SHM_FRACTION = 0.85


def _shm_available_nbytes(path: str = "/dev/shm") -> Optional[int]:
    try:
        st = os.statvfs(path)
        return int(st.f_bavail) * int(st.f_frsize)
    except Exception:
        return None


def compute_ring_slots(
    slot_nbytes: int,
    ram_fraction: float = DEFAULT_RAM_FRACTION,
    min_slots: int = MIN_RING_SLOTS,
    max_slots: int = MAX_RING_SLOTS,
    total_ram: Optional[int] = None,
    shm_nbytes: Optional[int] = None,
    shm_fraction: float = DEFAULT_SHM_FRACTION,
) -> int:
    """
    Size the science shm ring from total system RAM (and optional /dev/shm).

    ``n ≈ floor(total_ram * ram_fraction / slot_nbytes)``, also capped by
    ``floor(shm_nbytes * shm_fraction / slot_nbytes)`` when shm budget is known,
    then clamped to ``[min_slots, max_slots]``.
    """
    import psutil

    if total_ram is None:
        total_ram = int(psutil.virtual_memory().total)
    nbytes = max(int(slot_nbytes), 1)
    budget = int(float(total_ram) * float(ram_fraction))
    n = budget // nbytes
    if shm_nbytes is None:
        shm_nbytes = _shm_available_nbytes()
    if shm_nbytes is not None and int(shm_nbytes) > 0:
        shm_budget = int(float(shm_nbytes) * float(shm_fraction))
        n = min(n, shm_budget // nbytes)
    return int(max(min_slots, min(max_slots, n)))


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


def _slot_view(shm: shared_memory.SharedMemory, slot: int, slot_nbytes: int, shape, dtype):
    """Numpy view of one ring slot inside the contiguous slab."""
    off = int(slot) * int(slot_nbytes)
    mv = memoryview(shm.buf)[off : off + int(slot_nbytes)]
    return np.ndarray(shape, dtype=dtype, buffer=mv)


def storage_process_main(
    job_queue: mp.Queue,
    free_queue: mp.Queue,
    stats_queue: mp.Queue,
    shm_name: str,
    n_slots: int,
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

    shm: Optional[shared_memory.SharedMemory] = None
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
    except Exception:
        slog.exception("failed attaching shared memory %s", shm_name)
        return

    written = 0
    errors = 0
    slog.info(
        "storage process ready slots=%s nbytes=%s slab=%.1f MiB",
        n_slots,
        slot_nbytes,
        (n_slots * slot_nbytes) / (1024 * 1024),
    )

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
            if slot < 0 or slot >= n_slots or nbytes > slot_nbytes:
                slog.error(
                    "bad frame slot=%s nbytes=%s slot_nbytes=%s",
                    slot,
                    nbytes,
                    slot_nbytes,
                )
                errors += 1
                free_queue.put(slot)
                continue

            try:
                buf = _slot_view(shm, slot, slot_nbytes, shape, dtype)
                # Write directly from shm (no extra full-frame RAM copy).
                write_bayer_frame(
                    buf,
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
        if shm is not None:
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
    pending: int = 0  # slots currently held (awaiting / mid write)
    n_slots: int = 0


class ScienceStorageClient:
    """
    Parent-side client: owns one shm slab ring + child Process.

    ``publish`` never waits on disk — if no free slot, the frame is dropped.

    ``n_slots=None`` (default): auto-size ring to ~60% of total RAM / slot size
    (also capped by /dev/shm) when ``start()`` / ``ensure_capacity()`` runs.
    """

    def __init__(self, n_slots: Optional[int] = None, ram_fraction: float = DEFAULT_RAM_FRACTION):
        self._fixed_n_slots = None if n_slots is None else int(n_slots)
        self.ram_fraction = float(ram_fraction)
        self.n_slots = int(n_slots) if n_slots is not None else MIN_RING_SLOTS
        self._ctx = mp.get_context("spawn")
        self._job_q: Optional[mp.Queue] = None
        self._free_q: Optional[mp.Queue] = None
        self._stats_q: Optional[mp.Queue] = None
        self._proc: Optional[mp.Process] = None
        self._shm: Optional[shared_memory.SharedMemory] = None
        self._slot_nbytes = 0
        self._seq = 0
        self.stats = StorageStats(n_slots=self.n_slots)
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        was = self._enabled
        self._enabled = bool(enabled)
        if was and not self._enabled:
            log.info(
                "science save disarmed published=%s written=%s dropped=%s",
                self.stats.published,
                self.stats.written,
                self.stats.dropped,
            )
        elif not was and self._enabled:
            log.info("science save armed root will come from next publish")

    def free_slots(self) -> int:
        if self._free_q is None:
            return 0
        try:
            return int(self._free_q.qsize())
        except NotImplementedError:
            return 0

    def pending_slots(self) -> int:
        if self._proc is None or not self._proc.is_alive():
            return 0
        return max(0, self.n_slots - self.free_slots())

    def _resolve_n_slots(self, slot_nbytes: int) -> int:
        if self._fixed_n_slots is not None:
            return max(1, int(self._fixed_n_slots))
        return compute_ring_slots(slot_nbytes, ram_fraction=self.ram_fraction)

    def start(self, slot_nbytes: int) -> None:
        """Create ring + start storage process. Idempotent if already running same size."""
        slot_nbytes = int(slot_nbytes)
        if slot_nbytes < 64:
            raise ValueError("slot_nbytes too small")
        n_slots = self._resolve_n_slots(slot_nbytes)
        if (
            self._proc is not None
            and self._proc.is_alive()
            and self._shm is not None
            and slot_nbytes == self._slot_nbytes
            and n_slots == self.n_slots
        ):
            return
        self.shutdown()
        self.n_slots = n_slots
        self.stats.n_slots = n_slots
        self._slot_nbytes = slot_nbytes
        slab_nbytes = int(n_slots) * int(slot_nbytes)
        self._job_q = self._ctx.Queue()
        self._free_q = self._ctx.Queue()
        self._stats_q = self._ctx.Queue()
        try:
            shm = shared_memory.SharedMemory(create=True, size=slab_nbytes)
            self._shm = shm
            for i in range(self.n_slots):
                self._free_q.put(i)
            self._proc = self._ctx.Process(
                target=storage_process_main,
                args=(
                    self._job_q,
                    self._free_q,
                    self._stats_q,
                    shm.name,
                    self.n_slots,
                    slot_nbytes,
                ),
                name="cam-bayer-storage",
                daemon=True,
            )
            self._proc.start()
        except Exception:
            log.exception(
                "storage start failed slots=%s nbytes=%s slab=%.1f MiB; cleaning up",
                n_slots,
                slot_nbytes,
                slab_nbytes / (1024 * 1024),
            )
            self.shutdown()
            raise
        budget_mib = slab_nbytes / (1024 * 1024)
        log.info(
            "storage process started pid=%s slots=%s nbytes=%s (%.1f MiB slab, 1 shm fd, ram_fraction=%.2f%s)",
            self._proc.pid,
            self.n_slots,
            slot_nbytes,
            budget_mib,
            self.ram_fraction,
            "" if self._fixed_n_slots is None else ", fixed",
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
        if self._proc is None or not self._proc.is_alive() or self._shm is None:
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
            dest = _slot_view(self._shm, slot, self._slot_nbytes, arr.shape, arr.dtype)
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
        """Non-blocking pull of child written/error counters + pending depth."""
        if self._stats_q is None or self._job_q is None:
            self.stats.pending = self.pending_slots()
            self.stats.n_slots = self.n_slots
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
        self.stats.pending = self.pending_slots()
        self.stats.n_slots = self.n_slots
        return self.stats

    def shutdown(self, timeout: float = 2.0) -> None:
        proc = self._proc
        job_q = self._job_q
        shm = self._shm
        self._proc = None
        self._shm = None
        if proc is not None and proc.is_alive() and job_q is not None:
            try:
                job_q.put({"type": CMD_SHUTDOWN})
            except Exception:
                pass
            proc.join(timeout=timeout)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1.0)
        if shm is not None:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass
        self._job_q = None
        self._free_q = None
        self._stats_q = None
        self._slot_nbytes = 0
