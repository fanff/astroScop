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

export const PREVIEW_SCALES = [
  { div: 1, label: 'full' },
  { div: 2, label: '1/2' },
  { div: 4, label: '1/4' },
  { div: 8, label: '1/8' },
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
    preview_div: 2,
    save_format: 'none',
    save_section: 'test',
    save_subsection: '',
    save_enabled: false,
    save_root: './savedimgs',
    max_emit_fps: 8.0,
    locator_enabled: false,
    locator_x: 0.5,
    locator_y: 0.5,
    locator_size: 1.0,
    track_enabled: false,
    track_x: 0.5,
    track_y: 0.5,
    track_roi: 32,
    track_theta_deg: 0,
    track_flip_asc: false,
    track_flip_dec: false,
    guide_dec_deg: 0,
    guide_focal_mm: 18,
    guide_show_crop: false,
    guide_stack_n: 5,
    guide_kp: 0.80,
    guide_ki: 0.008,
  }
}

/** Map live CameraSettings → CAPTURE_MODES id (best match). */
export function captureModeIdFromSettings(settings = {}) {
  const preset = String(settings.sensor_preset || 'bin2x2')
  const mw = settings.main_width == null ? null : Number(settings.main_width)
  const mh = settings.main_height == null ? null : Number(settings.main_height)
  const exact = CAPTURE_MODES.find(
    (m) =>
      m.sensor_preset === preset &&
      m.main_width == mw &&
      m.main_height == mh
  )
  if (exact) return exact.id
  const native = CAPTURE_MODES.find(
    (m) => m.sensor_preset === preset && m.main_width == null
  )
  return (native || CAPTURE_MODES[5]).id
}

/** Map live preview_div → PREVIEW_SCALES div (1|2|4|8). */
export function previewDivFromSettings(settings = {}) {
  const d = Math.round(Number(settings.preview_div))
  if (d === 1 || d === 2 || d === 4 || d === 8) return d
  return 2
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
  out.preview_div = previewDivFromSettings(out)
  out.save_format = String(out.save_format || 'none')
  out.save_section = String(out.save_section || 'test')
  out.save_subsection = String(out.save_subsection || '')
  out.save_enabled = Boolean(out.save_enabled)
  out.save_root = String(out.save_root || './savedimgs')
  out.max_emit_fps = clamp(Number(out.max_emit_fps) || 8, 0.001, 60)
  out.locator_enabled = Boolean(out.locator_enabled)
  out.locator_x = clampNorm(out.locator_x)
  out.locator_y = clampNorm(out.locator_y)
  out.locator_size = clampLocatorSize(out.locator_size)
  out.track_enabled = Boolean(out.track_enabled)
  out.track_x = clampNorm(out.track_x)
  out.track_y = clampNorm(out.track_y)
  out.track_roi = clampTrackRoi(out.track_roi)
  out.track_theta_deg = clampTrackTheta(out.track_theta_deg)
  out.track_flip_asc = Boolean(out.track_flip_asc)
  out.track_flip_dec = Boolean(out.track_flip_dec)
  out.guide_dec_deg = clamp(Number(out.guide_dec_deg) || 0, -90, 90)
  const fmm = Number(out.guide_focal_mm)
  out.guide_focal_mm = Number.isFinite(fmm) ? Math.max(0, fmm) : 18
  out.guide_show_crop = Boolean(out.guide_show_crop)
  out.guide_stack_n = clampGuideStackN(out.guide_stack_n)
  out.guide_kp = clampGuideKp(out.guide_kp)
  out.guide_ki = clampGuideKi(out.guide_ki)

  // Drop legacy absolute display size if a partial still carries it.
  delete out.display_width
  delete out.display_height

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

/** Full-sensor normalized locator coordinate in [0, 1]. */
export function clampNorm(v, fallback = 0.5) {
  const n = Number(v)
  if (!Number.isFinite(n)) return fallback
  return clamp(n, 0, 1)
}

export const LOCATOR_STEP = 0.01
export const LOCATOR_SLIDER_STEPS = 1000

export function locatorToSlider(v) {
  return Math.round(clampNorm(v) * LOCATOR_SLIDER_STEPS)
}

export function sliderToLocator(pos) {
  const t = Math.min(LOCATOR_SLIDER_STEPS, Math.max(0, Number(pos) || 0))
  return t / LOCATOR_SLIDER_STEPS
}

export function formatLocatorPct(v) {
  return `${(clampNorm(v) * 100).toFixed(1)}%`
}

export const LOCATOR_SIZE_MIN = 0.15
export const LOCATOR_SIZE_MAX = 3.0
export const LOCATOR_SIZE_DEFAULT = 1.0

export function clampLocatorSize(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return LOCATOR_SIZE_DEFAULT
  return clamp(n, LOCATOR_SIZE_MIN, LOCATOR_SIZE_MAX)
}

export function formatLocatorSize(v) {
  return `×${clampLocatorSize(v).toFixed(2)}`
}

export const TRACK_ROI_MIN = 8
export const TRACK_ROI_MAX = 64
export const TRACK_ROI_DEFAULT = 32

export function clampTrackRoi(v) {
  const n = Math.round(Number(v))
  if (!Number.isFinite(n)) return TRACK_ROI_DEFAULT
  return Math.min(TRACK_ROI_MAX, Math.max(TRACK_ROI_MIN, n))
}

export const GUIDE_STACK_MIN = 1
export const GUIDE_STACK_MAX = 15
export const GUIDE_STACK_DEFAULT = 5

export function clampGuideStackN(v) {
  const n = Math.round(Number(v))
  if (!Number.isFinite(n)) return GUIDE_STACK_DEFAULT
  return Math.min(GUIDE_STACK_MAX, Math.max(GUIDE_STACK_MIN, n))
}

export const GUIDE_KP_MIN = 0
export const GUIDE_KP_MAX = 4
export const GUIDE_KP_DEFAULT = 0.80
export const GUIDE_KI_MIN = 0
export const GUIDE_KI_MAX = 0.5
export const GUIDE_KI_DEFAULT = 0.008

export function clampGuideKp(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return GUIDE_KP_DEFAULT
  return Math.min(GUIDE_KP_MAX, Math.max(GUIDE_KP_MIN, n))
}

export function clampGuideKi(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return GUIDE_KI_DEFAULT
  return Math.min(GUIDE_KI_MAX, Math.max(GUIDE_KI_MIN, n))
}

export function clampTrackTheta(v) {
  const n = Math.round(Number(v) / 90) * 90
  if (!Number.isFinite(n)) return 0
  const wrapped = ((n % 360) + 360) % 360
  return wrapped
}

export function defaultGuideSettings() {
  const d = defaultCameraSettings()
  return {
    track_enabled: d.track_enabled,
    track_x: d.track_x,
    track_y: d.track_y,
    track_roi: d.track_roi,
    track_theta_deg: d.track_theta_deg,
    track_flip_asc: d.track_flip_asc,
    track_flip_dec: d.track_flip_dec,
    guide_dec_deg: d.guide_dec_deg,
    guide_focal_mm: d.guide_focal_mm,
    guide_show_crop: d.guide_show_crop,
    guide_stack_n: d.guide_stack_n,
    guide_kp: d.guide_kp,
    guide_ki: d.guide_ki,
  }
}

export function pickGuideSettings(partial = {}) {
  const d = defaultGuideSettings()
  const src = { ...d, ...partial }
  return {
    track_enabled: Boolean(src.track_enabled),
    track_x: clampNorm(src.track_x),
    track_y: clampNorm(src.track_y),
    track_roi: clampTrackRoi(src.track_roi),
    track_theta_deg: clampTrackTheta(src.track_theta_deg),
    track_flip_asc: Boolean(src.track_flip_asc),
    track_flip_dec: Boolean(src.track_flip_dec),
    guide_dec_deg: clamp(Number(src.guide_dec_deg) || 0, -90, 90),
    guide_focal_mm: (() => {
      const fmm = Number(src.guide_focal_mm)
      return Number.isFinite(fmm) ? Math.max(0, fmm) : 18
    })(),
    guide_show_crop: Boolean(src.guide_show_crop),
    guide_stack_n: clampGuideStackN(src.guide_stack_n),
    guide_kp: clampGuideKp(src.guide_kp),
    guide_ki: clampGuideKi(src.guide_ki),
  }
}

export function captureSpaceKey(settings = {}) {
  const s = settings || {}
  const crop = Array.isArray(s.scaler_crop) ? s.scaler_crop.join(',') : ''
  return [
    String(s.sensor_preset || ''),
    s.main_width == null ? '' : String(s.main_width),
    s.main_height == null ? '' : String(s.main_height),
    String(previewDivFromSettings(s)),
    crop,
  ].join('|')
}
