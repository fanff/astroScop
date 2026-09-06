import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  TRACE_WINDOW_S,
  applyDump,
  appendRow,
  axisRange,
  csvFilename,
  pruneRows,
  rowFromGuideInfo,
  rowsFromPayload,
  strideRows,
  toCsv,
} from './guideTrace.js'

describe('guideTrace ring', () => {
  it('builds a row from guideInfo', () => {
    const row = rowFromGuideInfo({
      t: 1700000000,
      ok: true,
      e_asc_arcsec: -12.5,
      dAsc: 0.4,
      reason: '',
    })
    assert.equal(row.t, 1700000000)
    assert.equal(row.eAsc, -12.5)
    assert.equal(row.dAsc, 0.4)
    assert.equal(row.ok, true)
  })

  it('rebuilds rows from a columnar dump', () => {
    const rows = rowsFromPayload({
      t: [10, 10.2],
      ok: [true, false],
      eAsc: [1, 0],
      dAsc: [0.2, 0.2],
      reason: ['', 'too_few'],
    })
    assert.equal(rows.length, 2)
    assert.equal(rows[1].ok, false)
    assert.equal(rows[1].reason, 'too_few')
    assert.equal(rows[0].eAsc, 1)
  })

  it('prunes samples older than 20 minutes', () => {
    const now = 2000
    const rows = [
      { t: now - TRACE_WINDOW_S - 5, eAsc: 1 },
      { t: now - TRACE_WINDOW_S + 1, eAsc: 2 },
      { t: now, eAsc: 3 },
    ]
    pruneRows(rows, now)
    assert.equal(rows.length, 2)
    assert.equal(rows[0].eAsc, 2)
  })

  it('keeps live samples newer than a dump', () => {
    const dump = rowsFromPayload({ t: [100, 101], eAsc: [1, 2], dAsc: [0, 0] })
    const live = [{ t: 101.5, eAsc: 9, dAsc: 1, ok: true }]
    const merged = applyDump(live, dump, 101.5)
    assert.equal(merged.length, 3)
    assert.equal(merged[2].eAsc, 9)
  })

  it('appendRow prunes while growing', () => {
    const now = 5000
    const rows = []
    appendRow(rows, { t: now - TRACE_WINDOW_S - 10, eAsc: 1 }, now)
    appendRow(rows, { t: now, eAsc: 2 }, now)
    assert.equal(rows.length, 1)
    assert.equal(rows[0].eAsc, 2)
  })
})

describe('guideTrace chart helpers', () => {
  it('autoscales including zero', () => {
    const r = axisRange([2, 8])
    assert.ok(r.min < 0)
    assert.ok(r.max > 8)
  })

  it('handles a flat series', () => {
    const r = axisRange([0, 0, 0])
    assert.ok(r.min < 0)
    assert.ok(r.max > 0)
  })

  it('strides down to max points', () => {
    const rows = Array.from({ length: 5000 }, (_, i) => ({ t: i }))
    const drawn = strideRows(rows, 800)
    assert.ok(drawn.length <= 800)
    assert.equal(drawn[0].t, 0)
    assert.equal(drawn[drawn.length - 1].t, 4999)
  })
})

describe('guideTrace CSV', () => {
  it('writes a header and quoted reason', () => {
    const csv = toCsv([
      {
        t: 1700000000.25,
        ok: true,
        reason: 'a,b',
        eAsc: -1.5,
        eDec: 0.25,
        eAscPx: 0.1,
        eDecPx: 0,
        dAsc: 0.2,
        dDec: -0.05,
        snr: 11,
        nGated: 3,
        bin: 2,
        focalMm: 18,
        decDeg: 10,
        stackN: 5,
      },
    ])
    const lines = csv.trim().split('\n')
    assert.match(lines[0], /^t_iso,t,ok,reason/)
    assert.match(lines[1], /"a,b"/)
    assert.match(lines[1], /-1.5/)
    assert.match(lines[1], /,1,/)
  })

  it('names the download with a UTC stamp', () => {
    const name = csvFilename(new Date('2026-09-06T00:18:00.000Z'))
    assert.equal(name, 'guide_trace_20260906T001800Z.csv')
  })
})
