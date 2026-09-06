"""
Thin Pydantic envelopes for the camera ↔ rootserver ↔ UI WebSocket path.

Settings validation lives in ``cam_settings.CameraSettings``; this module only
wraps wire msgtypes the hub must understand first-class.

Motor ``ctlparams`` keys and guide sample/info shapes are named here so later
phases do not invent a second vocabulary. The hub still relays ``ctlparams``
opaquely; the motor worker owns the mixer.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cam_settings import CameraSettings, from_legacy_dict
from cam_spectrum import SpectrumStats

log = logging.getLogger("ws_messages")

# Size table for legacy shootresol → preset mapping (no picamera2 import).
SENSOR_PRESETS: Dict[str, Dict[str, Any]] = {
    "full": {"size": (4056, 3040)},
    "full_2160": {"size": (4056, 2160)},
    "bin2x2": {"size": (2028, 1520)},
    "bin2x2_1080": {"size": (2028, 1080)},
    "bin2x2_crop": {"size": (1332, 990)},
}


class ParamsMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    msgtype: str = "params"
    data: CameraSettings


class ServerOverwhelmedMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    msgtype: str = "serverOverwhelmed"
    data: bool


class CamTimingData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    imgbuffcount: int = 0  # preview MsgBuff depth (0/1)
    tosavecount: int = 0  # science pending slots (legacy name)
    science_published: int = 0
    science_dropped: int = 0
    science_written: int = 0
    science_errors: int = 0
    science_pending: int = 0
    science_slots: int = 0
    save_enabled: bool = False
    save_root: Optional[str] = None
    emitted: int = 0
    skipped: int = 0
    max_emit_fps: float = 8.0
    # Rates over the last ~3s timing window (wall-clock capture, not preview latency).
    capture_fps: float = 0.0
    frame_time_ms: float = 0.0
    science_publish_fps: float = 0.0
    science_write_fps: float = 0.0
    emit_fps: float = 0.0
    # Net fill ETA: free / max(0, publish_fps - write_fps); null when not filling.
    queue_fill_eta_s: Optional[float] = None


class CamTimingMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    msgtype: str = "camTiming"
    data: CamTimingData


class SrcImageMessage(BaseModel):
    """Camera → hub preview frame (flat envelope, not nested under data)."""

    model_config = ConfigDict(extra="ignore")

    msgtype: str = "srcimage"
    imageData: str
    usedParams: Dict[str, Any] = Field(default_factory=dict)
    spectrum: Optional[SpectrumStats] = None


def normalize_params_data(data: Any) -> CameraSettings:
    """
    Validate/normalize inbound params.data (legacy or canonical).

    Raises ValidationError / ValueError on bad payloads.
    """
    if isinstance(data, CameraSettings):
        return data
    if not isinstance(data, dict):
        raise ValueError(f"params.data must be a dict, got {type(data).__name__}")
    return from_legacy_dict(data, SENSOR_PRESETS)


def params_to_wire(settings: CameraSettings) -> str:
    """JSON string for msgtype params with canonical CameraSettings data."""
    return json.dumps({"msgtype": "params", "data": settings.to_wire_dict()})


def parse_srcimage(msg: Dict[str, Any]) -> SrcImageMessage:
    return SrcImageMessage.model_validate(msg)


def parse_cam_timing(msg: Dict[str, Any]) -> CamTimingMessage:
    return CamTimingMessage.model_validate(msg)


def hist_data_from_spectrum(spectrum: Union[SpectrumStats, Dict[str, Any]]) -> List[List[float]]:
    """
    Build legacy-compatible histData (3×256, log10) from SpectrumStats histograms.
    """
    if isinstance(spectrum, dict):
        spectrum = SpectrumStats.model_validate(spectrum)

    def _log_hist(vals: List[int]) -> List[float]:
        return [math.log10(float(v) + 1.0) for v in vals]

    return [_log_hist(spectrum.hist_r), _log_hist(spectrum.hist_g), _log_hist(spectrum.hist_b)]


# --- motor / guide wire names (Phase A) ---

CTL_ASC = "ASC"
CTL_DEC = "DEC"
CTL_ASC_SIDEREAL = "ASC_SIDEREAL"
CTL_MOTOR_ARM = "MOTOR_ARM"
CTL_MOTOR_DISARM = "MOTOR_DISARM"
CTL_ASC_ZERO = "ASC_ZERO"
CTL_DEC_ZERO = "DEC_ZERO"
CTL_ASC_RESET = "ASC_RESET"
CTL_DEC_RESET = "DEC_RESET"
CTL_ASC_CURR = "ASC_CURR"
CTL_DEC_CURR = "DEC_CURR"
CTL_GUIDE_ENABLE = "GUIDE_ENABLE"
CTL_GUIDE_DISABLE = "GUIDE_DISABLE"
CTL_GUIDE_DASC = "GUIDE_DASC"
CTL_GUIDE_DDEC = "GUIDE_DDEC"
CTL_GUIDE_TRACE_DUMP = "GUIDE_TRACE_DUMP"


class GuideSample(BaseModel):
    """Centroid sample from the guide worker (Phase E+). Hub fan-out is later."""

    model_config = ConfigDict(extra="ignore")

    msgtype: str = "guideSample"
    t: float = 0.0
    ok: bool = False
    u: float = 0.0
    v: float = 0.0
    lock_u: float = 0.0
    lock_v: float = 0.0
    roi_origin_u: float = 0.0
    roi_origin_v: float = 0.0
    snr: float = 0.0
    reason: str = ""
    n_gated: int = 0
    e_asc_arcsec: float = 0.0
    e_dec_arcsec: float = 0.0
    e_asc_steps: float = 0.0
    e_dec_steps: float = 0.0
    e_asc_px: float = 0.0
    e_dec_px: float = 0.0
    dAsc: float = 0.0
    dDec: float = 0.0
    dec_deg: float = 0.0
    focal_mm: float = 0.0
    preset: str = ""
    bin: int = 1
    stack_n: int = 5
    kp: float = 0.25
    ki: float = 0.02


class GuideInfo(BaseModel):
    """UI-facing guide status (subset of sample + lock flags)."""

    model_config = ConfigDict(extra="ignore")

    msgtype: str = "guideInfo"
    data: Dict[str, Any] = Field(default_factory=dict)


class MotorInfoGuideFields(BaseModel):
    """Extra motorInfo keys while the mixer is present (sliders stay on ff)."""

    model_config = ConfigDict(extra="ignore")

    guideEnabled: bool = False
    dAsc: float = 0.0
    dDec: float = 0.0
    ffAsc: float = 0.0
    ffDec: float = 0.0
    cmdAsc: float = 0.0
    cmdDec: float = 0.0


def try_normalize_params(data: Any) -> Optional[CameraSettings]:
    """Like normalize_params_data but logs and returns None on failure."""
    try:
        return normalize_params_data(data)
    except (ValidationError, ValueError, TypeError) as e:
        log.warning("invalid params ignored: %s", e)
        return None
    except Exception:
        log.exception("invalid params ignored")
        return None
