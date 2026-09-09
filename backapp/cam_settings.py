"""
Typed camera settings for the Pi HQ (IMX477) worker.

Canonical controls are non-overlapping: analogue gain is continuous;
isovalue/ISO are stripped on ingest and never applied. Slow fields require
stop/configure/start; fast fields use set_controls only.

Agent-facing contract (rootserver + UI): docs/camera-settings-contract.md
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Re-export for callers that historically imported SpectrumStats from here.
from cam_spectrum import SpectrumStats  # noqa: F401

SensorPresetName = Literal["full", "full_2160", "bin2x2", "bin2x2_1080", "bin2x2_crop"]

SLOW_FIELDS = frozenset(
    {
        "sensor_preset",
        "main_width",
        "main_height",
        "include_raw",
    }
)
FAST_FIELDS = frozenset(
    {
        "shutter_us",
        "analog_gain",
        "colour_gain_r",
        "colour_gain_b",
        "scaler_crop",
        "science_neutral",
    }
)
PreviewDiv = Literal[1, 2, 4, 8]
PREVIEW_DIVS = (1, 2, 4, 8)

OUTPUT_FIELDS = frozenset(
    {
        "preview_div",
        "save_format",
        "save_section",
        "save_subsection",
        "save_enabled",
        "save_root",
        "max_emit_fps",
        "locator_enabled",
        "locator_x",
        "locator_y",
        "locator_size",
        "track_enabled",
        "track_x",
        "track_y",
        "track_roi",
        "track_theta_deg",
        "track_flip_asc",
        "track_flip_dec",
        "guide_dec_deg",
        "guide_focal_mm",
        "guide_show_crop",
        "guide_stack_n",
        "guide_kp",
        "guide_ki",
    }
)


def preview_wh_from_frame(frame_wh: Tuple[int, int], preview_div: int) -> Tuple[int, int]:
    """
    Aspect-preserving integer downsample of capture RGB size for JPEG preview.

    Even dimensions (≥2) for encoder friendliness. ``preview_div`` is 1|2|4|8.
    """
    w, h = int(frame_wh[0]), int(frame_wh[1])
    d = int(preview_div) if int(preview_div) in PREVIEW_DIVS else 2
    out_w = max(2, (w // d) & ~1)
    out_h = max(2, (h // d) & ~1)
    return out_w, out_h

FORBIDDEN_CONTROL_KEYS = frozenset(
    {
        "isovalue",
        "iso",
        "ISO",
        "digital_gain",
        "digitalGain",
    }
)


class CameraSettings(BaseModel):
    """
    Full acquisition settings for the HQ camera worker.

    Slow: sensor_preset / main size / include_raw → reconfigure.
    Fast: exposure, analogue gain, colour gains, scaler crop → set_controls.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    sensor_preset: SensorPresetName = "bin2x2"
    main_width: Optional[int] = Field(default=None, ge=2)
    main_height: Optional[int] = Field(default=None, ge=2)
    include_raw: bool = True

    shutter_us: int = Field(default=150000, ge=1, le=600_000_000)
    analog_gain: float = Field(default=1.0, gt=0.0, le=64.0)
    colour_gain_r: float = Field(default=3.5, gt=0.0, le=32.0)
    colour_gain_b: float = Field(default=1.5, gt=0.0, le=32.0)
    scaler_crop: Optional[Tuple[int, int, int, int]] = None
    science_neutral: bool = True

    preview_div: PreviewDiv = 2
    save_format: str = "none"  # legacy: "none" | "npy" (Bayer only; RGB formats ignored)
    save_section: str = "test"
    save_subsection: str = ""
    save_enabled: bool = False
    save_root: str = "./savedimgs"
    max_emit_fps: float = Field(default=8.0, gt=0.0, le=60.0)
    # Preview-only tracking mark. X/Y are full IMX477 sensor fractions (0–1).
    locator_enabled: bool = False
    locator_x: float = Field(default=0.5, ge=0.0, le=1.0)
    locator_y: float = Field(default=0.5, ge=0.0, le=1.0)
    locator_size: float = Field(default=1.0, ge=0.15, le=3.0)
    # Tracking lock: native RGB crop for the guide worker (not the composition glyph).
    track_enabled: bool = False
    track_x: float = Field(default=0.5, ge=0.0, le=1.0)
    track_y: float = Field(default=0.5, ge=0.0, le=1.0)
    track_roi: int = Field(default=32, ge=8, le=64)
    track_theta_deg: float = 0.0
    track_flip_asc: bool = False
    track_flip_dec: bool = False
    guide_dec_deg: float = Field(default=0.0, ge=-90.0, le=90.0)
    guide_focal_mm: float = Field(default=18.0, ge=0.0, le=10000.0)
    guide_show_crop: bool = False
    guide_stack_n: int = Field(default=5, ge=1, le=15)
    guide_kp: float = Field(default=0.80, ge=0.0, le=4.0)
    guide_ki: float = Field(default=0.008, ge=0.0, le=0.5)

    def science_save_active(self) -> bool:
        """Runtime switch: arm Bayer persistence (not RGB/JPEG)."""
        if self.save_enabled:
            return True
        return self.save_format in ("npy", "bayer")

    @field_validator("scaler_crop")
    @classmethod
    def _even_crop(cls, v):
        if v is None:
            return v
        x, y, w, h = (int(v[0]), int(v[1]), int(v[2]), int(v[3]))
        w -= w % 2
        h -= h % 2
        if w < 2 or h < 2:
            raise ValueError("scaler_crop width/height must be >= 2")
        return (x, y, w, h)

    @model_validator(mode="after")
    def _pair_main_size(self):
        if (self.main_width is None) ^ (self.main_height is None):
            raise ValueError("main_width and main_height must both be set or both null")
        return self

    def resolved_main_size(self, presets: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
        """Return main stream (width, height), defaulting to the sensor preset size."""
        if self.main_width is not None and self.main_height is not None:
            return int(self.main_width), int(self.main_height)
        size = presets[self.sensor_preset]["size"]
        return int(size[0]), int(size[1])

    def to_wire_dict(self) -> Dict[str, Any]:
        """Clean outbound settings (no ISO / digital gain controls)."""
        return self.model_dump(mode="json")

    def to_legacy_worker_dict(self, presets: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bridge for configure helpers that still expect legacy dict keys.

        Never encodes ISO as a live control (isovalue forced to 0).
        """
        mw, mh = self.resolved_main_size(presets)
        return {
            "shutterSpeed": int(self.shutter_us),
            "analog_gain": float(self.analog_gain),
            "isovalue": 0,
            "redgain": float(self.colour_gain_r),
            "bluegain": float(self.colour_gain_b),
            "digital_gain": 1.0,
            "expomode": "off",
            "shootresol": {
                "name": self.sensor_preset,
                "width": mw,
                "height": mh,
                "mode": 0,
            },
            "dispresol": {
                "name": "display",
                "width": 0,
                "height": 0,
                "mode": 0,
            },
            "preview_div": int(self.preview_div),
            "denoise": False,
            "capture_format": "rgb",
            "exposure_compensation": 0,
            "brightness": 50,
            "saturation": 0,
            "contrast": 0,
            "sharpness": 0,
            "save_format": self.save_format,
            "save_section": self.save_section,
            "save_subsection": self.save_subsection,
            "save_enabled": self.science_save_active(),
            "save_root": self.save_root,
            "cameraZoom": 0,
            "crop": (0, 0, 1, 1),
            "sensor_preset": self.sensor_preset,
            "include_raw": self.include_raw,
            "scaler_crop": self.scaler_crop,
            "science_neutral": self.science_neutral,
            "max_emit_fps": self.max_emit_fps,
            "locator_enabled": self.locator_enabled,
            "locator_x": self.locator_x,
            "locator_y": self.locator_y,
            "locator_size": self.locator_size,
            "track_enabled": self.track_enabled,
            "track_x": self.track_x,
            "track_y": self.track_y,
            "track_roi": self.track_roi,
            "track_theta_deg": self.track_theta_deg,
            "track_flip_asc": self.track_flip_asc,
            "track_flip_dec": self.track_flip_dec,
            "guide_dec_deg": self.guide_dec_deg,
            "guide_focal_mm": self.guide_focal_mm,
            "guide_show_crop": self.guide_show_crop,
            "guide_stack_n": self.guide_stack_n,
            "guide_kp": self.guide_kp,
            "guide_ki": self.guide_ki,
        }


class SettingsDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slow_changed: bool
    fast_changed: bool
    output_changed: bool
    changed_fields: List[str]


def diff_settings(old: CameraSettings, new: CameraSettings) -> SettingsDiff:
    """Classify which apply path(s) a settings change requires."""
    changed = []
    old_d = old.model_dump()
    new_d = new.model_dump()
    for k in old_d:
        if old_d[k] != new_d[k]:
            changed.append(k)
    return SettingsDiff(
        slow_changed=any(k in SLOW_FIELDS for k in changed),
        fast_changed=any(k in FAST_FIELDS for k in changed),
        output_changed=any(k in OUTPUT_FIELDS for k in changed),
        changed_fields=changed,
    )


def _strip_forbidden(data: Dict[str, Any]) -> List[str]:
    """Remove forbidden overlapping controls; return names that were stripped."""
    stripped = []
    for k in list(data.keys()):
        if k in FORBIDDEN_CONTROL_KEYS:
            data.pop(k)
            stripped.append(k)
    return stripped


def from_legacy_dict(
    data: Optional[Dict[str, Any]],
    presets: Dict[str, Dict[str, Any]],
) -> CameraSettings:
    """
    Ingest rootserver/wasp blobs into CameraSettings.

    Maps shutterSpeed → shutter_us, redgain/bluegain → colour gains.
    Strips isovalue/iso/digital_gain — they are never used as controls.
    """
    if data is None:
        return CameraSettings()

    raw = dict(data)
    stripped = _strip_forbidden(raw)
    if stripped:
        logging.getLogger("cam_settings").warning(
            "stripped forbidden control key(s) %s (use analog_gain only)",
            stripped,
        )

    kwargs: Dict[str, Any] = {}

    if "sensor_preset" in raw:
        kwargs["sensor_preset"] = raw["sensor_preset"]
    elif "shootresol" in raw and isinstance(raw["shootresol"], dict):
        sr = raw["shootresol"]
        name = sr.get("name")
        if name in ("full", "full_2160", "bin2x2", "bin2x2_1080", "bin2x2_crop"):
            kwargs["sensor_preset"] = name
        w, h = sr.get("width"), sr.get("height")
        if w and h:
            for pname, pinfo in presets.items():
                if tuple(pinfo["size"]) == (int(w), int(h)):
                    kwargs["sensor_preset"] = pname
                    break
            else:
                kwargs["main_width"] = int(w)
                kwargs["main_height"] = int(h)

    if "main_width" in raw:
        kwargs["main_width"] = raw["main_width"]
    if "main_height" in raw:
        kwargs["main_height"] = raw["main_height"]
    if "include_raw" in raw:
        kwargs["include_raw"] = bool(raw["include_raw"])

    if "shutter_us" in raw:
        kwargs["shutter_us"] = int(raw["shutter_us"])
    elif "shutterSpeed" in raw:
        kwargs["shutter_us"] = int(raw["shutterSpeed"])

    if "analog_gain" in raw:
        kwargs["analog_gain"] = float(raw["analog_gain"])

    if "colour_gain_r" in raw:
        kwargs["colour_gain_r"] = float(raw["colour_gain_r"])
    elif "redgain" in raw:
        kwargs["colour_gain_r"] = float(raw["redgain"])

    if "colour_gain_b" in raw:
        kwargs["colour_gain_b"] = float(raw["colour_gain_b"])
    elif "bluegain" in raw:
        kwargs["colour_gain_b"] = float(raw["bluegain"])

    if "scaler_crop" in raw and raw["scaler_crop"] is not None:
        sc = raw["scaler_crop"]
        kwargs["scaler_crop"] = tuple(int(x) for x in sc)

    if "science_neutral" in raw:
        kwargs["science_neutral"] = bool(raw["science_neutral"])

    # Canonical preview scale. Legacy display_width/height / dispresol are ignored
    # (absolute boxes distorted aspect); default preview_div=2 applies.
    if "preview_div" in raw:
        try:
            pd = int(raw["preview_div"])
            if pd in PREVIEW_DIVS:
                kwargs["preview_div"] = pd
        except (TypeError, ValueError):
            pass

    for k in ("save_format", "save_section", "save_subsection", "save_root"):
        if k in raw:
            kwargs[k] = raw[k]
    if "save_enabled" in raw:
        kwargs["save_enabled"] = bool(raw["save_enabled"])
    elif raw.get("save_format") in ("npy", "bayer"):
        kwargs["save_enabled"] = True
        kwargs["save_format"] = "npy"
    elif raw.get("save_format") == "none":
        kwargs["save_enabled"] = False
    if "max_emit_fps" in raw:
        kwargs["max_emit_fps"] = float(raw["max_emit_fps"])
    if "locator_enabled" in raw:
        kwargs["locator_enabled"] = bool(raw["locator_enabled"])
    if "locator_x" in raw:
        kwargs["locator_x"] = float(raw["locator_x"])
    if "locator_y" in raw:
        kwargs["locator_y"] = float(raw["locator_y"])
    if "locator_size" in raw:
        kwargs["locator_size"] = float(raw["locator_size"])
    if "track_enabled" in raw:
        kwargs["track_enabled"] = bool(raw["track_enabled"])
    if "track_x" in raw:
        kwargs["track_x"] = float(raw["track_x"])
    if "track_y" in raw:
        kwargs["track_y"] = float(raw["track_y"])
    if "track_roi" in raw:
        kwargs["track_roi"] = int(raw["track_roi"])
    if "track_theta_deg" in raw:
        kwargs["track_theta_deg"] = float(raw["track_theta_deg"])
    if "track_flip_asc" in raw:
        kwargs["track_flip_asc"] = bool(raw["track_flip_asc"])
    if "track_flip_dec" in raw:
        kwargs["track_flip_dec"] = bool(raw["track_flip_dec"])
    if "guide_dec_deg" in raw:
        kwargs["guide_dec_deg"] = float(raw["guide_dec_deg"])
    if "guide_focal_mm" in raw:
        kwargs["guide_focal_mm"] = float(raw["guide_focal_mm"])
    if "guide_show_crop" in raw:
        kwargs["guide_show_crop"] = bool(raw["guide_show_crop"])
    if "guide_stack_n" in raw:
        kwargs["guide_stack_n"] = int(raw["guide_stack_n"])
    if "guide_kp" in raw:
        kwargs["guide_kp"] = float(raw["guide_kp"])
    if "guide_ki" in raw:
        kwargs["guide_ki"] = float(raw["guide_ki"])

    return CameraSettings(**kwargs)


def default_settings() -> CameraSettings:
    return CameraSettings()
