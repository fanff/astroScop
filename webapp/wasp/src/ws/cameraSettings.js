/**
 * Canonical CameraSettings wire shape — mirrors backapp/cam_settings.py.
 * UI must emit these keys only (no legacy shutterSpeed / redgain / ISO).
 */

export const SENSOR_PRESETS = [
  {
    value: 'bin2x2_crop',
    label: 'fast · 1332×990 (center crop 2×2)',
    hint: 'highest frame rate — smaller FOV',
  },
  {
    value: 'bin2x2_1080',
    label: '2028×1080 (2×2 16:9)',
    hint: 'binned, cropped height',
  },
  {
    value: 'bin2x2',
    label: '2028×1520 (2×2 full FOV)',
    hint: 'default science mode',
  },
  {
    value: 'full_2160',
    label: '4056×2160 (1×1 16:9)',
    hint: 'full-width 16:9 crop',
  },
  {
    value: 'full',
    label: 'slow · 4056×3040 (full 1×1)',
    hint: 'max detail, slowest readout',
  },
]

/**
 * ~12 capture profiles → sensor_preset + optional main_* (RGB stream size).
 * Sensor size drives Bayer readout speed; smaller main_* lightens ISP/JPEG.
 */
export const CAPTURE_MODES = [
  {
    id: 'crop_1332',
    label: '1 · fast crop 1332×990 (sensor)',
    sensor_preset: 'bin2x2_crop',
    main_width: null,
    main_height: null,
  },
  {
    id: 'crop_666',
    label: '2 · fast crop · RGB 666×494',
    sensor_preset: 'bin2x2_crop',
    main_width: 666,
    main_height: 494,
  },
  {
    id: 'crop_444',
    label: '3 · fast crop · RGB 444×330',
    sensor_preset: 'bin2x2_crop',
    main_width: 444,
    main_height: 330,
  },
  {
    id: 'b1080_2028',
    label: '4 · bin2x2 16:9 2028×1080',
    sensor_preset: 'bin2x2_1080',
    main_width: null,
    main_height: null,
  },
  {
    id: 'b1080_1014',
    label: '5 · bin2x2 16:9 · RGB 1014×540',
    sensor_preset: 'bin2x2_1080',
    main_width: 1014,
    main_height: 540,
  },
  {
    id: 'bin_2028',
    label: '6 · bin2x2 full FOV 2028×1520',
    sensor_preset: 'bin2x2',
    main_width: null,
    main_height: null,
  },
  {
    id: 'bin_1014',
    label: '7 · bin2x2 · RGB 1014×760',
    sensor_preset: 'bin2x2',
    main_width: 1014,
    main_height: 760,
  },
  {
    id: 'bin_640',
    label: '8 · bin2x2 · RGB 640×480',
    sensor_preset: 'bin2x2',
    main_width: 640,
    main_height: 480,
  },
  {
    id: 'f2160_4056',
    label: '9 · full 16:9 4056×2160',
    sensor_preset: 'full_2160',
    main_width: null,
    main_height: null,
  },
  {
    id: 'f2160_2028',
    label: '10 · full 16:9 · RGB 2028×1080',
    sensor_preset: 'full_2160',
    main_width: 2028,
    main_height: 1080,
  },
  {
    id: 'full_4056',
    label: '11 · full 4056×3040 (slow)',
    sensor_preset: 'full',
    main_width: null,
    main_height: null,
  },
  {
    id: 'full_2028',
    label: '12 · full · RGB 2028×1520',
    sensor_preset: 'full',
    main_width: 2028,
    main_height: 1520,
  },
]

export const DISPLAY_PRESETS = [
  { width: 320, height: 240, label: '320×240 (light preview)' },
  { width: 640, height: 480, label: '640×480' },
  { width: 960, height: 720, label: '960×720' },
  { width: 1280, height: 720, label: '1280×720' },
  { width: 1920, height: 1080, label: '1920×1080' },
]

export const SAVE_SECTIONS = ['test', 'work', 'deep', 'planet', 'dark', 'flats']

/** UI shutter span: 1 µs … 2 minutes (log slider). Backend allows up to 600 s. */
export const SHUTTER_US_MIN = 1
export const SHUTTER_US_MAX = 120_000_000
export const SHUTTER_LOG_STEPS = 1000

/** Colour gain log slider: (0, 32] — practical UI floor 0.1 */
export const COLOUR_GAIN_MIN = 0.1
export const COLOUR_GAIN_MAX = 32
export const COLOUR_GAIN_LOG_STEPS = 1000
export const COLOUR_GAIN_R_DEFAULT = 3.5
export const COLOUR_GAIN_B_DEFAULT = 1.5

const LOG_MIN = Math.log(SHUTTER_US_MIN)
const LOG_MAX = Math.log(SHUTTER_US_MAX)
const LOG_SPAN = LOG_MAX - LOG_MIN

const CG_LOG_MIN = Math.log(COLOUR_GAIN_MIN)
const CG_LOG_MAX = Math.log(COLOUR_GAIN_MAX)
const CG_LOG_SPAN = CG_LOG_MAX - CG_LOG_MIN

export function clampShutterUs(us) {
  const n = Math.round(Number(us))
  if (!Number.isFinite(n)) return SHUTTER_US_MIN
  return Math.min(SHUTTER_US_MAX, Math.max(SHUTTER_US_MIN, n))
}

/** Map shutter_us → integer log slider position [0, SHUTTER_LOG_STEPS]. */
export function shutterUsToLogPos(us) {
  const v = clampShutterUs(us)
  const t = (Math.log(v) - LOG_MIN) / LOG_SPAN
  return Math.round(t * SHUTTER_LOG_STEPS)
}

/** Map log slider position → shutter_us. */
export function shutterLogPosToUs(pos) {
  const t = Math.min(SHUTTER_LOG_STEPS, Math.max(0, Number(pos) || 0)) / SHUTTER_LOG_STEPS
  return clampShutterUs(Math.exp(LOG_MIN + t * LOG_SPAN))
}

export function clampColourGain(g) {
  const n = Number(g)
  if (!Number.isFinite(n)) return COLOUR_GAIN_MIN
  return Math.min(COLOUR_GAIN_MAX, Math.max(COLOUR_GAIN_MIN, n))
}

export function colourGainToLogPos(g) {
  const v = clampColourGain(g)
  const t = (Math.log(v) - CG_LOG_MIN) / CG_LOG_SPAN
  return Math.round(t * COLOUR_GAIN_LOG_STEPS)
}

export function colourGainLogPosToGain(pos) {
  const t =
    Math.min(COLOUR_GAIN_LOG_STEPS, Math.max(0, Number(pos) || 0)) /
    COLOUR_GAIN_LOG_STEPS
  return clampColourGain(Math.exp(CG_LOG_MIN + t * CG_LOG_SPAN))
}

/** Human-readable exposure for night UI. */
export function formatShutterUs(us) {
  const v = clampShutterUs(us)
  if (v < 1000) return `${v} µs`
  if (v < 1_000_000) {
    const ms = v / 1000
    return ms >= 100 ? `${ms.toFixed(0)} ms` : `${ms.toFixed(2)} ms`
  }
  const sec = v / 1_000_000
  if (sec < 60) {
    return sec >= 10 ? `${sec.toFixed(1)} s` : `${sec.toFixed(3)} s`
  }
  const m = Math.floor(sec / 60)
  const s = sec - m * 60
  return s < 0.05 ? `${m} min` : `${m}m ${s.toFixed(0)}s`
}

/** Backend defaults from CameraSettings. */
export function defaultCameraSettings() {
  return {
    sensor_preset: 'bin2x2',
    main_width: null,
    main_height: null,
    include_raw: true,
    shutter_us: 150000,
    analog_gain: 1.0,
    colour_gain_r: COLOUR_GAIN_R_DEFAULT,
    colour_gain_b: COLOUR_GAIN_B_DEFAULT,
    scaler_crop: null,
    science_neutral: true,
    display_width: 640,
    display_height: 480,
    save_format: 'none',
    save_section: 'test',
    save_subsection: '',
    save_enabled: false,
    save_root: './savedimgs',
    max_emit_fps: 8.0,
  }
}

/**
 * Build a clean wire dict (only known fields, coerced types).
 * @param {Partial<ReturnType<typeof defaultCameraSettings>>} partial
 */
export function toWireSettings(partial = {}) {
  const base = defaultCameraSettings()
  const out = { ...base, ...partial }

  out.sensor_preset = String(out.sensor_preset || 'bin2x2')
  out.include_raw = Boolean(out.include_raw)
  out.shutter_us = Math.max(1, Math.round(Number(out.shutter_us) || 1))
  out.analog_gain = clamp(Number(out.analog_gain) || 1, 0.001, 64)
  out.colour_gain_r = clamp(Number(out.colour_gain_r) || COLOUR_GAIN_R_DEFAULT, 0.001, 32)
  out.colour_gain_b = clamp(Number(out.colour_gain_b) || COLOUR_GAIN_B_DEFAULT, 0.001, 32)
  out.science_neutral = Boolean(out.science_neutral)
  out.display_width = Math.max(2, Math.round(Number(out.display_width) || 640))
  out.display_height = Math.max(2, Math.round(Number(out.display_height) || 480))
  out.save_format = String(out.save_format || 'none')
  out.save_section = String(out.save_section || 'test')
  out.save_subsection = String(out.save_subsection || '')
  out.save_enabled = Boolean(out.save_enabled)
  out.save_root = String(out.save_root || './savedimgs')
  out.max_emit_fps = clamp(Number(out.max_emit_fps) || 8, 0.001, 60)

  if (out.main_width == null || out.main_height == null) {
    out.main_width = null
    out.main_height = null
  } else {
    out.main_width = Math.max(2, Math.round(Number(out.main_width)))
    out.main_height = Math.max(2, Math.round(Number(out.main_height)))
  }

  if (Array.isArray(out.scaler_crop) && out.scaler_crop.length === 4) {
    out.scaler_crop = out.scaler_crop.map((v) => Math.round(Number(v)))
  } else {
    out.scaler_crop = null
  }

  return out
}

function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v))
}
