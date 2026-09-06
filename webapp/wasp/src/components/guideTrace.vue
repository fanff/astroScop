<template>
  <div class="panel guide-trace">
    <div class="trace-head">
      <span class="panelTitle">tracking trace</span>
      <span class="trace-meta">{{ spanLabel }}</span>
      <button type="button" class="trace-dl" :disabled="!rows.length" @click="onDownload">
        download CSV
      </button>
    </div>
    <p v-if="!rows.length" class="hint">Waiting for guide samples…</p>
    <div v-else class="charts">
      <div class="chart-block">
        <div class="chart-label">ASC · error (left, arcsec) · trim (right, STEP/s)</div>
        <canvas ref="asc" class="chart" height="140"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">DEC · error (left, arcsec) · trim (right, STEP/s)</div>
        <canvas ref="dec" class="chart" height="140"></canvas>
      </div>
    </div>
  </div>
</template>

<script>
import {
  axisRange,
  downloadCsv,
  strideRows,
} from '../ws/guideTrace.js'

const PAD = { top: 8, right: 44, bottom: 18, left: 44 }
const COL_ERR = '#c7221c'
const COL_TRIM = '#ffb000'
const COL_AXIS = 'rgba(138, 42, 38, 0.7)'
const COL_ZERO = 'rgba(199, 34, 28, 0.35)'
const COL_GRID = 'rgba(122, 26, 22, 0.22)'

function mapX(t, t0, t1, w) {
  const span = t1 - t0 || 1
  return PAD.left + ((t - t0) / span) * (w - PAD.left - PAD.right)
}

function mapY(v, min, max, h) {
  const span = max - min || 1
  return PAD.top + (1 - (v - min) / span) * (h - PAD.top - PAD.bottom)
}

function drawLine(ctx, pts, color, dashed) {
  if (pts.length < 2) return
  ctx.save()
  ctx.beginPath()
  ctx.strokeStyle = color
  ctx.lineWidth = 1.25
  if (dashed) ctx.setLineDash([3, 3])
  let drawing = false
  for (const p of pts) {
    if (p == null) {
      drawing = false
      continue
    }
    if (!drawing) {
      ctx.moveTo(p.x, p.y)
      drawing = true
    } else {
      ctx.lineTo(p.x, p.y)
    }
  }
  ctx.stroke()
  ctx.restore()
}

function fmtTick(v) {
  const a = Math.abs(v)
  if (a >= 100) return v.toFixed(0)
  if (a >= 10) return v.toFixed(1)
  return v.toFixed(2)
}

function fmtSpan(s) {
  if (!Number.isFinite(s) || s <= 0) return '0s'
  if (s < 90) return `${Math.round(s)}s`
  const m = Math.floor(s / 60)
  const r = Math.round(s - m * 60)
  return r ? `${m}m ${r}s` : `${m}m`
}

export default {
  name: 'guideTrace',
  props: {
    rows: { type: Array, default: () => [] },
  },
  computed: {
    spanLabel() {
      if (!this.rows.length) return '0 samples'
      const t0 = this.rows[0].t
      const t1 = this.rows[this.rows.length - 1].t
      return `${this.rows.length} samples · ${fmtSpan(t1 - t0)}`
    },
    drawKey() {
      if (!this.rows.length) return '0'
      const last = this.rows[this.rows.length - 1]
      return `${this.rows.length}:${last.t}`
    },
  },
  watch: {
    drawKey() {
      this.$nextTick(() => this.scheduleDraw())
    },
  },
  mounted() {
    this._ro = new ResizeObserver(() => this.scheduleDraw())
    this._ro.observe(this.$el)
    this.scheduleDraw()
  },
  beforeUnmount() {
    if (this._ro) this._ro.disconnect()
    if (this._raf) cancelAnimationFrame(this._raf)
  },
  methods: {
    onDownload() {
      downloadCsv(this.rows)
    },
    scheduleDraw() {
      if (this._raf) cancelAnimationFrame(this._raf)
      this._raf = requestAnimationFrame(() => {
        this._raf = 0
        this.drawAll()
      })
    },
    drawAll() {
      this.drawAxis(this.$refs.asc, 'eAsc', 'dAsc')
      this.drawAxis(this.$refs.dec, 'eDec', 'dDec')
    },
    drawAxis(canvas, errKey, trimKey) {
      if (!canvas || !this.rows.length) return
      const cssW = Math.max(canvas.clientWidth || canvas.parentElement.clientWidth || 300, 80)
      const cssH = 140
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.round(cssW * dpr)
      canvas.height = Math.round(cssH * dpr)
      canvas.style.width = cssW + 'px'
      canvas.style.height = cssH + 'px'
      const ctx = canvas.getContext('2d')
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, cssW, cssH)

      const drawn = strideRows(this.rows)
      const t0 = drawn[0].t
      const t1 = drawn[drawn.length - 1].t
      const errVals = drawn.filter((r) => r.ok).map((r) => r[errKey])
      const trimVals = drawn.map((r) => r[trimKey])
      const errR = axisRange(errVals.length ? errVals : [0])
      const trimR = axisRange(trimVals)

      const plotW = cssW - PAD.left - PAD.right
      const plotH = cssH - PAD.top - PAD.bottom

      ctx.fillStyle = 'rgba(0,0,0,0.35)'
      ctx.fillRect(PAD.left, PAD.top, plotW, plotH)

      ctx.strokeStyle = COL_GRID
      ctx.lineWidth = 1
      for (let i = 0; i <= 4; i++) {
        const y = PAD.top + (plotH * i) / 4
        ctx.beginPath()
        ctx.moveTo(PAD.left, y)
        ctx.lineTo(PAD.left + plotW, y)
        ctx.stroke()
      }

      const yErr0 = mapY(0, errR.min, errR.max, cssH)
      ctx.strokeStyle = COL_ZERO
      ctx.beginPath()
      ctx.moveTo(PAD.left, yErr0)
      ctx.lineTo(PAD.left + plotW, yErr0)
      ctx.stroke()

      const errPts = drawn.map((r) => {
        if (!r.ok) return null
        return {
          x: mapX(r.t, t0, t1, cssW),
          y: mapY(r[errKey], errR.min, errR.max, cssH),
        }
      })
      const trimPts = drawn.map((r) => ({
        x: mapX(r.t, t0, t1, cssW),
        y: mapY(r[trimKey], trimR.min, trimR.max, cssH),
      }))
      drawLine(ctx, trimPts, COL_TRIM, true)
      drawLine(ctx, errPts, COL_ERR, false)

      ctx.font = '10px monospace, sans-serif'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = COL_ERR
      ctx.textAlign = 'right'
      ctx.fillText(fmtTick(errR.max), PAD.left - 4, PAD.top)
      ctx.fillText(fmtTick(errR.min), PAD.left - 4, PAD.top + plotH)
      ctx.fillStyle = COL_TRIM
      ctx.textAlign = 'left'
      ctx.fillText(fmtTick(trimR.max), PAD.left + plotW + 4, PAD.top)
      ctx.fillText(fmtTick(trimR.min), PAD.left + plotW + 4, PAD.top + plotH)

      ctx.fillStyle = COL_AXIS
      ctx.textAlign = 'left'
      ctx.textBaseline = 'top'
      ctx.fillText(fmtSpan(0), PAD.left, cssH - 14)
      ctx.textAlign = 'right'
      ctx.fillText(fmtSpan(t1 - t0), PAD.left + plotW, cssH - 14)
    },
  },
}
</script>

<style scoped>
.guide-trace {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 8px 10px 10px;
  text-align: left;
  color: var(--fg, #c7221c);
}
.trace-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.panelTitle {
  font-size: 12px;
  color: var(--fg-dim, #8a2a26);
  text-transform: lowercase;
}
.trace-meta {
  font-size: 11px;
  font-family: monospace, sans-serif;
  color: var(--fg-dim, #8a2a26);
  flex: 1 1 auto;
}
.trace-dl {
  font-size: 12px;
  padding: 1px 8px;
  margin-left: auto;
}
.hint {
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  margin: 6px 0 0;
}
.charts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 6px;
}
.chart-block {
  min-width: 0;
}
.chart-label {
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  margin-bottom: 2px;
}
.chart {
  display: block;
  width: 100%;
  height: 140px;
}
</style>
