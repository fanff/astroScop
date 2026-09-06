"""One-tile isolate → geom → PI. No camera, no hub."""

from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image

from guide_geom import bin_factor_for_preset, pixels_to_axis_steps
from guide_handoff import GuideTile
from guide_isolate import CentroidEma, TileStack, isolate_star
from guide_pid import DEADBAND_PX, KD, KI, KP, GuidePI, clamp_ki, clamp_kp
from ws_messages import GuideSample


@dataclass
class GuideConfig:
    f_mm: float = 18.0
    dec_deg: float = 0.0
    theta_deg: float = 0.0
    flip_asc: bool = False
    flip_dec: bool = False
    preset: str = "bin2x2"
    bin: int = 0  # 0 → from preset
    show_crop: bool = False
    stack_n: int = 5
    kp: float = KP
    ki: float = KI

    def resolved_bin(self) -> int:
        if int(self.bin) in (1, 2):
            return int(self.bin)
        return bin_factor_for_preset(self.preset)


def config_from_settings(data: dict) -> GuideConfig:
    """Map CameraSettings / params wire dict into GuideConfig."""
    raw = dict(data or {})
    preset = str(raw.get("sensor_preset") or "bin2x2")
    try:
        f_mm = float(raw.get("guide_focal_mm", 18.0))
    except (TypeError, ValueError):
        f_mm = 0.0
    try:
        dec_deg = float(raw.get("guide_dec_deg", 0.0))
    except (TypeError, ValueError):
        dec_deg = 0.0
    try:
        theta = float(raw.get("track_theta_deg", 0.0))
    except (TypeError, ValueError):
        theta = 0.0
    return GuideConfig(
        f_mm=f_mm,
        dec_deg=dec_deg,
        theta_deg=theta,
        flip_asc=bool(raw.get("track_flip_asc", False)),
        flip_dec=bool(raw.get("track_flip_dec", False)),
        preset=preset,
        bin=0,
        show_crop=bool(raw.get("guide_show_crop", False)),
        stack_n=_clamp_stack_n(raw.get("guide_stack_n", 5)),
        kp=clamp_kp(raw.get("guide_kp", KP)),
        ki=clamp_ki(raw.get("guide_ki", KI)),
    )


def _clamp_stack_n(raw) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 5
    return max(1, min(15, n))


@dataclass
class ProcessResult:
    sample: GuideSample
    jpeg: Optional[bytes] = None
    skipped: bool = False


class GuideEngine:
    def __init__(self, cfg: Optional[GuideConfig] = None) -> None:
        self.cfg = cfg or GuideConfig()
        self.ema = CentroidEma(n=3)
        self.stack = TileStack(n=self.cfg.stack_n)
        self.pid = GuidePI()
        self.pid.set_gains(self.cfg.kp, self.cfg.ki)
        self.last_t: Optional[float] = None
        self.last_seq: Optional[int] = None
        if abs(KD) > 0:
            raise RuntimeError("Phase E ships PI-only; Kd must stay 0")

    def apply_config(self, cfg: GuideConfig) -> None:
        old_n = int(self.cfg.stack_n)
        self.cfg = cfg
        if int(cfg.stack_n) != old_n:
            self.stack = TileStack(n=self.cfg.stack_n)
        self.pid.set_gains(cfg.kp, cfg.ki)

    def reset(self) -> None:
        """Clear PI / EMA so arming the mixer does not dump a wound I-term."""
        self.pid.reset()
        self.ema = CentroidEma(n=3)
        self.stack = TileStack(n=self.cfg.stack_n)
        self.last_t = None

    def process_tile(
        self,
        tile: GuideTile,
        *,
        seq: Optional[int] = None,
        jpeg: bool = False,
        now: Optional[float] = None,
    ) -> ProcessResult:
        if seq is not None and self.last_seq is not None and int(seq) == int(self.last_seq):
            return ProcessResult(sample=self._empty(tile, now), skipped=True)
        if seq is not None:
            self.last_seq = int(seq)

        t = float(tile.t if now is None else now)
        dt = 0.2 if self.last_t is None else (t - self.last_t)
        if dt <= 0:
            dt = 0.2
        self.last_t = t

        sample = self._empty(tile, t)
        if self.cfg.f_mm <= 0:
            sample.ok = False
            sample.reason = "no_focal"
            d_asc, d_dec = self.pid.note_miss(t)
            sample.dAsc, sample.dDec = d_asc, d_dec
            return ProcessResult(sample=sample, jpeg=self._jpeg(tile.rgb) if jpeg else None)

        work = self.stack.push(tile.rgb)
        iso = isolate_star(work, tile.lock_u, tile.lock_v)
        sample.snr = float(iso.snr)
        sample.reason = str(iso.reason or "")
        sample.n_gated = int(iso.n_gated)
        jpeg_bytes = self._jpeg(work) if jpeg else None
        if not iso.ok:
            sample.ok = False
            sample.u, sample.v = float(iso.u), float(iso.v)
            d_asc, d_dec = self.pid.note_miss(t)
            sample.dAsc, sample.dDec = d_asc, d_dec
            return ProcessResult(sample=sample, jpeg=jpeg_bytes)

        u, v = self.ema.update(iso.u, iso.v)
        sample.ok = True
        sample.u, sample.v = float(u), float(v)
        e_u = float(tile.lock_u) - float(u)
        e_v = float(tile.lock_v) - float(v)
        in_deadband = math.hypot(e_u, e_v) <= DEADBAND_PX
        err = pixels_to_axis_steps(
            e_u,
            e_v,
            f_mm=self.cfg.f_mm,
            bin=self.cfg.resolved_bin(),
            dec_deg=self.cfg.dec_deg,
            theta_deg=self.cfg.theta_deg,
            flip_asc=self.cfg.flip_asc,
            flip_dec=self.cfg.flip_dec,
        )
        sample.e_asc_arcsec = err.e_asc_arcsec
        sample.e_dec_arcsec = err.e_dec_arcsec
        sample.e_asc_steps = err.e_asc_steps
        sample.e_dec_steps = err.e_dec_steps
        sample.e_asc_px = err.e_asc_px
        sample.e_dec_px = err.e_dec_px
        self.pid.note_ok()
        d_asc, d_dec = self.pid.update(
            err.e_asc_px,
            err.e_dec_px,
            dt,
            pole_gate=err.pole_gate,
            in_deadband=in_deadband,
        )
        sample.dAsc = d_asc
        sample.dDec = d_dec
        return ProcessResult(sample=sample, jpeg=jpeg_bytes)

    def _empty(self, tile: GuideTile, t: Optional[float]) -> GuideSample:
        return GuideSample(
            t=float(tile.t if t is None else t),
            ok=False,
            u=float(tile.lock_u),
            v=float(tile.lock_v),
            lock_u=float(tile.lock_u),
            lock_v=float(tile.lock_v),
            roi_origin_u=float(tile.origin_u),
            roi_origin_v=float(tile.origin_v),
            dec_deg=float(self.cfg.dec_deg),
            focal_mm=float(self.cfg.f_mm),
            preset=self.cfg.preset,
            bin=self.cfg.resolved_bin() if self.cfg.f_mm > 0 else 1,
            stack_n=int(self.cfg.stack_n),
            kp=float(self.cfg.kp),
            ki=float(self.cfg.ki),
        )

    @staticmethod
    def _jpeg(rgb) -> bytes:
        buf = BytesIO()
        arr = np.clip(np.round(np.asarray(rgb)), 0, 255).astype(np.uint8)
        Image.fromarray(arr).save(buf, format="JPEG", quality=70)
        return buf.getvalue()
