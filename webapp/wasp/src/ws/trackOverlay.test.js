import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  locatorPreviewXy,
  previewXyToFullSensor,
  imageContentRect,
  clientPointToPreviewPx,
  axisUnits,
  overlayPercent,
} from './trackOverlay.js'

describe('preview ↔ full-sensor', () => {
  it('round-trips inside a scaler crop', () => {
    const crop = [200, 100, 2000, 1500]
    const wh = [640, 480]
    for (const [nx, ny] of [
      [0.3, 0.4],
      [0.5, 0.45],
      [0.2, 0.2],
    ]) {
      const [px, py] = locatorPreviewXy(nx, ny, wh, crop)
      const back = previewXyToFullSensor(px, py, wh, crop)
      assert.ok(Math.abs(back[0] - nx) < 1e-9)
      assert.ok(Math.abs(back[1] - ny) < 1e-9)
    }
  })
})

describe('object-fit contain click', () => {
  it('maps the JPEG center through letterboxing', () => {
    const elRect = { left: 0, top: 0, width: 400, height: 200 }
    const content = imageContentRect(elRect, 200, 200)
    assert.equal(content.width, 200)
    assert.equal(content.height, 200)
    assert.equal(content.left, 100)
    assert.equal(content.top, 0)
    const mid = clientPointToPreviewPx(200, 100, content)
    assert.ok(mid)
    assert.ok(Math.abs(mid.px - 99.5) < 1e-6)
    assert.ok(Math.abs(mid.py - 99.5) < 1e-6)
    assert.equal(clientPointToPreviewPx(10, 100, content), null)
  })

  it('places overlay percent inside the wrap', () => {
    const wrap = { left: 0, top: 0, width: 400, height: 200 }
    const content = imageContentRect(wrap, 200, 200)
    const pct = overlayPercent(content, wrap)
    assert.equal(pct.left, 25)
    assert.equal(pct.top, 0)
    assert.equal(pct.width, 50)
    assert.equal(pct.height, 100)
  })
})

describe('axis arrows', () => {
  it('θ=0: ASC+ right, DEC+ down', () => {
    const u = axisUnits(0, false, false)
    assert.ok(Math.abs(u.asc[0] - 1) < 1e-9)
    assert.ok(Math.abs(u.asc[1]) < 1e-9)
    assert.ok(Math.abs(u.dec[0]) < 1e-9)
    assert.ok(Math.abs(u.dec[1] - 1) < 1e-9)
  })
})
