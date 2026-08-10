"""
Thin Pydantic envelopes for the camera ↔ rootserver ↔ UI WebSocket path.

Settings validation lives in ``cam_settings.CameraSettings``; this module only
wraps wire msgtypes the hub must understand first-class.
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
