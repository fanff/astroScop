/**
 * Full-sensor lock ↔ preview JPEG mapping (mirrors backapp/cam_locator.py).
 */

export const FULL_SENSOR_WH = [4056, 3040]

export const SENSOR_CAPTURE_WH = {
  full: [4056, 3040],
  full_2160: [4056, 2160],
  bin2x2: [2028, 1520],
  bin2x2_1080: [2028, 1080],
  bin2x2_crop: [1332, 990],
}

export function clamp01(v, fallback = 0.5) {
  const n = Number(v)
  if (!Number.isFinite(n)) return fallback
  return Math.min(1, Math.max(0, n))
}

export function parseScalerCrop(crop, fullWh = FULL_SENSOR_WH) {
  const fw = fullWh[0]
  const fh = fullWh[1]
  if (!Array.isArray(crop) || crop.length !== 4) return [0, 0, fw, fh]
  const x = Math.round(Number(crop[0]))
  const y = Math.round(Number(crop[1]))
  const w = Math.round(Number(crop[2]))
  const h = Math.round(Number(crop[3]))
  if (!Number.isFinite(w) || !Number.isFinite(h) || w < 1 || h < 1) {
    return [0, 0, fw, fh]
  }
  return [x, y, w, h]
}

export function locatorPreviewXy(
  nx,
  ny,
  previewWh,
  scalerCrop = null,
  fullWh = FULL_SENSOR_WH
) {
  const fw = fullWh[0]
  const fh = fullWh[1]
  const [cx, cy, cw, ch] = parseScalerCrop(scalerCrop, fullWh)
  const sx = clamp01(nx) * fw
  const sy = clamp01(ny) * fh
  let relX = (sx - cx) / cw
  let relY = (sy - cy) / ch
  relX = Math.min(1, Math.max(0, relX))
  relY = Math.min(1, Math.max(0, relY))
  const pw = previewWh[0]
  const ph = previewWh[1]
  const px = pw > 1 ? relX * (pw - 1) : 0
  const py = ph > 1 ? relY * (ph - 1) : 0
  return [px, py]
}

export function previewXyToFullSensor(
  px,
  py,
  previewWh,
  scalerCrop = null,
  fullWh = FULL_SENSOR_WH
) {
  const fw = fullWh[0]
  const fh = fullWh[1]
  const [cx, cy, cw, ch] = parseScalerCrop(scalerCrop, fullWh)
  const pw = previewWh[0]
  const ph = previewWh[1]
  let relX = pw > 1 ? Number(px) / (pw - 1) : 0.5
  let relY = ph > 1 ? Number(py) / (ph - 1) : 0.5
  relX = Math.min(1, Math.max(0, relX))
  relY = Math.min(1, Math.max(0, relY))
  const sx = cx + relX * cw
  const sy = cy + relY * ch
  const nx = fw ? sx / fw : 0.5
  const ny = fh ? sy / fh : 0.5
  return [clamp01(nx), clamp01(ny)]
}

/**
 * Visible JPEG rectangle inside an object-fit:contain <img> box.
 * All numbers in CSS pixels of the same coordinate space as getBoundingClientRect.
 */
export function imageContentRect(elRect, naturalWidth, naturalHeight) {
  const nw = Math.max(1, Number(naturalWidth) || 1)
  const nh = Math.max(1, Number(naturalHeight) || 1)
  const boxW = elRect.width
  const boxH = elRect.height
  const scale = Math.min(boxW / nw, boxH / nh)
  const width = nw * scale
  const height = nh * scale
  return {
    left: elRect.left + (boxW - width) / 2,
    top: elRect.top + (boxH - height) / 2,
    width,
    height,
    naturalWidth: nw,
    naturalHeight: nh,
  }
}

export function clientPointToPreviewPx(clientX, clientY, contentRect) {
  const x = clientX - contentRect.left
  const y = clientY - contentRect.top
  if (x < 0 || y < 0 || x > contentRect.width || y > contentRect.height) {
    return null
  }
  const pw = contentRect.naturalWidth
  const ph = contentRect.naturalHeight
  const px = contentRect.width > 0 ? (x / contentRect.width) * (pw - 1) : 0
  const py = contentRect.height > 0 ? (y / contentRect.height) * (ph - 1) : 0
  return { px, py }
}

export function overlayPercent(contentRect, wrapRect) {
  if (!wrapRect.width || !wrapRect.height) {
    return { left: 0, top: 0, width: 100, height: 100 }
  }
  return {
    left: ((contentRect.left - wrapRect.left) / wrapRect.width) * 100,
    top: ((contentRect.top - wrapRect.top) / wrapRect.height) * 100,
    width: (contentRect.width / wrapRect.width) * 100,
    height: (contentRect.height / wrapRect.height) * 100,
  }
}

/** ASC+ / DEC+ unit vectors in image +u/+v (right, down). θ=0: ASC+=+u, DEC+=+v. */
export function axisUnits(thetaDeg, flipAsc, flipDec) {
  const th = (Number(thetaDeg) || 0) * (Math.PI / 180)
  const c = Math.cos(th)
  const s = Math.sin(th)
  let ax = c
  let ay = s
  let dx = -s
  let dy = c
  if (flipAsc) {
    ax = -ax
    ay = -ay
  }
  if (flipDec) {
    dx = -dx
    dy = -dy
  }
  return { asc: [ax, ay], dec: [dx, dy] }
}

export function captureWh(settings = {}) {
  const preset = String(settings.sensor_preset || 'bin2x2')
  const native = SENSOR_CAPTURE_WH[preset] || SENSOR_CAPTURE_WH.bin2x2
  const mw = settings.main_width
  const mh = settings.main_height
  if (mw != null && mh != null) {
    return [Math.max(2, Number(mw)), Math.max(2, Number(mh))]
  }
  return native
}

export function lockBoxPreviewPx(trackRoi, previewWh, settings = {}) {
  const [cw, ch] = captureWh(settings)
  const pw = previewWh[0]
  const ph = previewWh[1]
  const half = Math.max(8, Number(trackRoi) || 32)
  const sx = cw > 0 ? pw / cw : 1
  const sy = ch > 0 ? ph / ch : 1
  return [2 * half * sx, 2 * half * sy]
}
