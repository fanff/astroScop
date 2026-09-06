import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  guideEnableAllowed,
  guideEnableBlockReason,
  guideMixerKeepAllowed,
} from './guideEnable.js'

const ok = {
  motor: { armed: true, connected: true },
  guide: { ok: true },
  settings: { track_enabled: true, guide_focal_mm: 400 },
}

describe('guideEnableAllowed', () => {
  it('allows when all gates hold', () => {
    assert.equal(guideEnableAllowed(ok), true)
    assert.equal(guideEnableBlockReason(ok), '')
  })

  it('blocks without motor arm', () => {
    assert.equal(
      guideEnableAllowed({ ...ok, motor: { armed: false, connected: true } }),
      false
    )
    assert.match(
      guideEnableBlockReason({ ...ok, motor: { armed: false, connected: true } }),
      /arm motors/
    )
  })

  it('blocks without Pico', () => {
    assert.equal(
      guideEnableAllowed({ ...ok, motor: { armed: true, connected: false } }),
      false
    )
  })

  it('blocks without lock', () => {
    assert.equal(
      guideEnableAllowed({
        ...ok,
        settings: { track_enabled: false, guide_focal_mm: 400 },
      }),
      false
    )
  })

  it('blocks f_mm <= 0', () => {
    assert.equal(
      guideEnableAllowed({
        ...ok,
        settings: { track_enabled: true, guide_focal_mm: 0 },
      }),
      false
    )
  })

  it('blocks when star not ok', () => {
    assert.equal(guideEnableAllowed({ ...ok, guide: { ok: false } }), false)
    assert.equal(guideEnableAllowed({ ...ok, guide: null }), false)
  })

  it('keeps mixer through lost star', () => {
    assert.equal(
      guideMixerKeepAllowed({ ...ok, guide: { ok: false } }),
      true
    )
  })

  it('drops keep without arm', () => {
    assert.equal(
      guideMixerKeepAllowed({
        motor: { armed: false, connected: true },
        settings: ok.settings,
      }),
      false
    )
  })
})
