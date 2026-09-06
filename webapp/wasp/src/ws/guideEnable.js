/**
 * Mixer arm gates — wasp must not send GUIDE_ENABLE unless these hold.
 * Motor worker also refuses enable without UI arm + Pico.
 *
 * Lost-star (`guide.ok`) blocks *first* enable only. The motor already
 * holds then zeros trims; unchecking the mixer on every flicker leaves
 * commanded = feedforward forever.
 */

export function guideMixerKeepReason({ motor = {}, settings = {} } = {}) {
  if (!motor || !motor.armed) return 'arm motors first'
  if (!motor.connected) return 'Pico not linked'
  if (!settings || !settings.track_enabled) return 'enable tracking lock'
  const fmm = Number(settings.guide_focal_mm)
  if (!Number.isFinite(fmm) || fmm <= 0) return 'set focal length (mm)'
  return ''
}

export function guideMixerKeepAllowed(args = {}) {
  return guideMixerKeepReason(args) === ''
}

export function guideEnableBlockReason({
  motor = {},
  guide = {},
  settings = {},
} = {}) {
  const keep = guideMixerKeepReason({ motor, settings })
  if (keep) return keep
  if (!guide || guide.ok !== true) return 'wait for a locked star (ok)'
  return ''
}

export function guideEnableAllowed(args = {}) {
  return guideEnableBlockReason(args) === ''
}
