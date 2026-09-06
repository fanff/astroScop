"""Rolling 20-minute autoguide trace: memory ring + CSV on disk."""

from __future__ import annotations

import csv
import logging
import math
import os
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

log = logging.getLogger("guide_trace")

WINDOW_S = 1200.0
FLUSH_EVERY_S = 10.0

DEFAULT_CSV = Path(__file__).resolve().parent / "savedimgs" / "guide_trace.csv"

CSV_COLUMNS = (
    "t_iso",
    "t",
    "ok",
    "reason",
    "e_asc_arcsec",
    "e_dec_arcsec",
    "e_asc_px",
    "e_dec_px",
    "dAsc",
    "dDec",
    "snr",
    "n_gated",
    "bin",
    "focal_mm",
    "dec_deg",
    "stack_n",
)

# Columnar WS payload keys (parallel arrays, same order as the deque).
PAYLOAD_FIELDS = (
    ("t", "t"),
    ("ok", "ok"),
    ("reason", "reason"),
    ("eAsc", "e_asc_arcsec"),
    ("eDec", "e_dec_arcsec"),
    ("eAscPx", "e_asc_px"),
    ("eDecPx", "e_dec_px"),
    ("dAsc", "dAsc"),
    ("dDec", "dDec"),
    ("snr", "snr"),
    ("nGated", "n_gated"),
    ("bin", "bin"),
    ("focalMm", "focal_mm"),
    ("decDeg", "dec_deg"),
    ("stackN", "stack_n"),
)


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _i(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _bool(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "ok")
    return bool(v)


def t_iso(t: float) -> str:
    try:
        dt = datetime.fromtimestamp(float(t), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def row_from_sample(sample: Any) -> Optional[dict]:
    """Build a ring row from a GuideSample or dict. None if t is unusable."""
    if sample is None:
        return None
    if hasattr(sample, "model_dump"):
        data = sample.model_dump()
    elif isinstance(sample, Mapping):
        data = sample
    else:
        return None
    t = _f(data.get("t"), default=float("nan"))
    if not math.isfinite(t) or t <= 0:
        return None
    return {
        "t": t,
        "ok": _bool(data.get("ok")),
        "reason": str(data.get("reason") or ""),
        "e_asc_arcsec": _f(data.get("e_asc_arcsec")),
        "e_dec_arcsec": _f(data.get("e_dec_arcsec")),
        "e_asc_px": _f(data.get("e_asc_px")),
        "e_dec_px": _f(data.get("e_dec_px")),
        "dAsc": _f(data.get("dAsc")),
        "dDec": _f(data.get("dDec")),
        "snr": _f(data.get("snr")),
        "n_gated": _i(data.get("n_gated")),
        "bin": _i(data.get("bin"), default=1),
        "focal_mm": _f(data.get("focal_mm")),
        "dec_deg": _f(data.get("dec_deg")),
        "stack_n": _i(data.get("stack_n"), default=1),
    }


class GuideTraceBuffer:
    """Last ``window_s`` of samples, optionally flushed to CSV."""

    def __init__(
        self,
        window_s: float = WINDOW_S,
        csv_path: Optional[os.PathLike[str] | str] = None,
        flush_every_s: float = FLUSH_EVERY_S,
    ) -> None:
        self.window_s = float(window_s)
        self.csv_path = Path(csv_path) if csv_path is not None else DEFAULT_CSV
        self.flush_every_s = float(flush_every_s)
        self._rows: deque[dict] = deque()
        self._last_flush_mono = 0.0

    def __len__(self) -> int:
        return len(self._rows)

    def append(self, sample: Any, now: Optional[float] = None) -> Optional[dict]:
        row = row_from_sample(sample)
        if row is None:
            return None
        self._rows.append(row)
        self.prune(now if now is not None else row["t"])
        return row

    def prune(self, now: float) -> None:
        cut = float(now) - self.window_s
        rows = self._rows
        while rows and rows[0]["t"] < cut:
            rows.popleft()

    def to_payload(self) -> dict:
        rows = self._rows
        payload = {"n": len(rows), "window_s": self.window_s}
        for wire, src in PAYLOAD_FIELDS:
            payload[wire] = [r[src] for r in rows]
        return payload

    def maybe_flush(self, now_mono: Optional[float] = None) -> bool:
        t_mono = time.monotonic() if now_mono is None else float(now_mono)
        if self._last_flush_mono and (t_mono - self._last_flush_mono) < self.flush_every_s:
            return False
        ok = self.flush()
        if ok:
            self._last_flush_mono = t_mono
        return ok

    def flush(self) -> bool:
        path = self.csv_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix="guide_trace.", suffix=".csv", dir=str(path.parent)
            )
            try:
                with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
                    w.writeheader()
                    for row in self._rows:
                        out = dict(row)
                        out["t_iso"] = t_iso(row["t"])
                        out["ok"] = 1 if row["ok"] else 0
                        w.writerow(out)
                os.replace(tmp_name, path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except Exception:
            log.warning("guide_trace CSV flush failed (%s)", path, exc_info=True)
            return False
        return True


def rows_from_payload(payload: Mapping[str, Any]) -> list[dict]:
    """Rebuild row dicts from a columnar guideTrace payload (tests / UI parity)."""
    t_list = payload.get("t") or []
    n = len(t_list)
    rows = []
    for i in range(n):
        row = {}
        for wire, src in PAYLOAD_FIELDS:
            seq = payload.get(wire) or []
            row[src] = seq[i] if i < len(seq) else None
        if row.get("t"):
            rows.append(row)
    return rows


def iter_csv_dicts(path: os.PathLike[str] | str) -> Iterable[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)
