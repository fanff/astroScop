/**
 * Rolling 20-minute autoguide trace (browser ring + CSV).
 * Columnar dump keys match backapp/guide_trace.py PAYLOAD_FIELDS.
 */

export const TRACE_WINDOW_S = 1200
export const TRACE_DRAW_MAX = 800

export const CSV_COLUMNS = [
  't_iso',
  't',
  'ok',
  'reason',
  'e_asc_arcsec',
  'e_dec_arcsec',
  'e_asc_px',
  'e_dec_px',
  'dAsc',
  'dDec',
  'snr',
  'n_gated',
  'bin',
  'focal_mm',
  'dec_deg',
  'stack_n',
]

function num(v, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function tIso(t) {
  const n = Number(t)
  if (!Number.isFinite(n) || n <= 0) return ''
  return new Date(n * 1000).toISOString()
}

export function rowFromGuideInfo(data) {
  if (!data || typeof data !== 'object') return null
  let t = num(data.t, NaN)
  if (!Number.isFinite(t) || t <= 0) {
    t = Date.now() / 1000
  }
  return {
    t,
    ok: Boolean(data.ok),
    reason: data.reason != null ? String(data.reason) : '',
    eAsc: num(data.e_asc_arcsec),
    eDec: num(data.e_dec_arcsec),
    eAscPx: num(data.e_asc_px),
    eDecPx: num(data.e_dec_px),
    dAsc: num(data.dAsc),
    dDec: num(data.dDec),
    snr: num(data.snr),
    nGated: num(data.n_gated),
    bin: num(data.bin, 1),
    focalMm: num(data.focal_mm),
    decDeg: num(data.dec_deg),
    stackN: num(data.stack_n, 1),
  }
}

export function rowsFromPayload(data) {
  if (!data || typeof data !== 'object') return []
  const tList = Array.isArray(data.t) ? data.t : []
  const rows = []
  for (let i = 0; i < tList.length; i++) {
    const t = num(tList[i], NaN)
    if (!Number.isFinite(t) || t <= 0) continue
    rows.push({
      t,
      ok: Boolean((data.ok || [])[i]),
      reason: String((data.reason || [])[i] || ''),
      eAsc: num((data.eAsc || [])[i]),
      eDec: num((data.eDec || [])[i]),
      eAscPx: num((data.eAscPx || [])[i]),
      eDecPx: num((data.eDecPx || [])[i]),
      dAsc: num((data.dAsc || [])[i]),
      dDec: num((data.dDec || [])[i]),
      snr: num((data.snr || [])[i]),
      nGated: num((data.nGated || [])[i]),
      bin: num((data.bin || [])[i], 1),
      focalMm: num((data.focalMm || [])[i]),
      decDeg: num((data.decDeg || [])[i]),
      stackN: num((data.stackN || [])[i], 1),
    })
  }
  return rows
}

export function pruneRows(rows, nowS = Date.now() / 1000) {
  const cut = nowS - TRACE_WINDOW_S
  let i = 0
  while (i < rows.length && rows[i].t < cut) i += 1
  if (i > 0) rows.splice(0, i)
  return rows
}

export function appendRow(rows, row, nowS = Date.now() / 1000) {
  if (!row) return rows
  rows.push(row)
  return pruneRows(rows, nowS)
}

/** Replace with dump, keep any live samples newer than the dump tail. */
export function applyDump(rows, dumpRows, nowS = Date.now() / 1000) {
  const lastDumpT = dumpRows.length ? dumpRows[dumpRows.length - 1].t : 0
  const live = rows.filter((r) => r.t > lastDumpT)
  const merged = dumpRows.concat(live)
  return pruneRows(merged, nowS)
}

export function strideRows(rows, maxPoints = TRACE_DRAW_MAX) {
  if (!rows.length || rows.length <= maxPoints) return rows
  const step = (rows.length - 1) / (maxPoints - 1)
  const out = []
  let prev = -1
  for (let i = 0; i < maxPoints; i++) {
    const idx = Math.round(i * step)
    if (idx === prev) continue
    prev = idx
    out.push(rows[idx])
  }
  return out
}

export function axisRange(values, { includeZero = true, pad = 0.08 } = {}) {
  const nums = values.filter((v) => Number.isFinite(v))
  if (!nums.length) return { min: -1, max: 1 }
  let min = Math.min(...nums)
  let max = Math.max(...nums)
  if (includeZero) {
    min = Math.min(min, 0)
    max = Math.max(max, 0)
  }
  if (min === max) {
    min -= 1
    max += 1
  }
  const span = max - min
  const extra = span * pad
  return { min: min - extra, max: max + extra }
}

function csvEscape(v) {
  const s = v == null ? '' : String(v)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export function toCsv(rows) {
  const lines = [CSV_COLUMNS.join(',')]
  for (const r of rows) {
    const rec = {
      t_iso: tIso(r.t),
      t: r.t,
      ok: r.ok ? 1 : 0,
      reason: r.reason || '',
      e_asc_arcsec: r.eAsc,
      e_dec_arcsec: r.eDec,
      e_asc_px: r.eAscPx,
      e_dec_px: r.eDecPx,
      dAsc: r.dAsc,
      dDec: r.dDec,
      snr: r.snr,
      n_gated: r.nGated,
      bin: r.bin,
      focal_mm: r.focalMm,
      dec_deg: r.decDeg,
      stack_n: r.stackN,
    }
    lines.push(CSV_COLUMNS.map((k) => csvEscape(rec[k])).join(','))
  }
  return lines.join('\n') + '\n'
}

export function csvFilename(date = new Date()) {
  const iso = date.toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')
  return `guide_trace_${iso}.csv`
}

export function downloadCsv(rows, filename = csvFilename()) {
  const blob = new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
