"""GuideTraceBuffer unit tests (no camera / hub)."""

import os
import time
from pathlib import Path

from guide_trace import (
    WINDOW_S,
    GuideTraceBuffer,
    row_from_sample,
    rows_from_payload,
    t_iso,
)
from ws_messages import GuideSample


def _sample(t, *, ok=True, e_asc=1.0, d_asc=0.2, **kwargs):
    return GuideSample(
        t=t,
        ok=ok,
        e_asc_arcsec=e_asc,
        e_dec_arcsec=kwargs.get("e_dec", -0.5),
        e_asc_px=kwargs.get("e_px", 0.3),
        e_dec_px=kwargs.get("e_dec_px", -0.1),
        dAsc=d_asc,
        dDec=kwargs.get("d_dec", -0.05),
        snr=kwargs.get("snr", 12.0),
        n_gated=kwargs.get("n_gated", 4),
        bin=kwargs.get("bin", 2),
        focal_mm=kwargs.get("focal_mm", 18.0),
        dec_deg=kwargs.get("dec_deg", 42.0),
        stack_n=kwargs.get("stack_n", 5),
        reason=kwargs.get("reason", ""),
    )


def test_row_from_sample_and_iso():
    row = row_from_sample(_sample(1_700_000_000.0, e_asc=-12.5))
    assert row is not None
    assert row["t"] == 1_700_000_000.0
    assert row["e_asc_arcsec"] == -12.5
    assert row["ok"] is True
    iso = t_iso(row["t"])
    assert iso.endswith("Z")
    assert "T" in iso
    assert row_from_sample({"t": 0}) is None
    assert row_from_sample({"ok": True}) is None


def test_prune_drops_older_than_window(tmp_path: Path):
    buf = GuideTraceBuffer(window_s=WINDOW_S, csv_path=tmp_path / "t.csv")
    t0 = 2_000_000_000.0
    buf.append(_sample(t0 - WINDOW_S - 5), now=t0)
    buf.append(_sample(t0 - WINDOW_S + 1, e_asc=2.0), now=t0)
    buf.append(_sample(t0, e_asc=3.0), now=t0)
    assert len(buf) == 2
    assert buf._rows[0]["e_asc_arcsec"] == 2.0
    assert buf._rows[-1]["e_asc_arcsec"] == 3.0


def test_payload_columnar_roundtrip(tmp_path: Path):
    buf = GuideTraceBuffer(window_s=60, csv_path=tmp_path / "t.csv")
    t0 = 1_800_000_000.0
    buf.append(_sample(t0, e_asc=1.25, d_asc=-0.4))
    buf.append(_sample(t0 + 0.2, ok=False, reason="too_few", e_asc=0.0, d_asc=-0.4))
    payload = buf.to_payload()
    assert payload["n"] == 2
    assert payload["eAsc"] == [1.25, 0.0]
    assert payload["dAsc"] == [-0.4, -0.4]
    assert payload["ok"] == [True, False]
    assert payload["reason"][1] == "too_few"
    rebuilt = rows_from_payload(payload)
    assert len(rebuilt) == 2
    assert rebuilt[0]["e_asc_arcsec"] == 1.25
    assert rebuilt[1]["ok"] is False


def test_csv_flush_roundtrip(tmp_path: Path):
    path = tmp_path / "guide_trace.csv"
    buf = GuideTraceBuffer(window_s=60, csv_path=path, flush_every_s=0.0)
    t0 = 1_800_000_123.456
    buf.append(_sample(t0, e_asc=-8.0, d_asc=1.5, reason="ok"))
    assert buf.flush() is True
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0].startswith("t_iso,t,")
    assert "e_asc_arcsec" in lines[0]
    assert "-8.0" in lines[1] or "-8" in lines[1]
    assert "1.5" in lines[1]
    # rewrite is atomic-enough: flush twice still one header
    buf.append(_sample(t0 + 1.0, e_asc=0.5))
    buf.flush()
    text2 = path.read_text(encoding="utf-8")
    header_count = sum(1 for ln in text2.splitlines() if ln.startswith("t_iso,"))
    assert header_count == 1
    assert text2.count("\n") >= 3


def test_maybe_flush_rate_limit(tmp_path: Path):
    path = tmp_path / "guide_trace.csv"
    buf = GuideTraceBuffer(window_s=60, csv_path=path, flush_every_s=10.0)
    buf.append(_sample(1_800_000_000.0))
    assert buf.maybe_flush(now_mono=100.0) is True
    mtime = os.path.getmtime(path)
    time.sleep(0.05)
    buf.append(_sample(1_800_000_001.0))
    assert buf.maybe_flush(now_mono=105.0) is False
    assert os.path.getmtime(path) == mtime
    assert buf.maybe_flush(now_mono=111.0) is True
