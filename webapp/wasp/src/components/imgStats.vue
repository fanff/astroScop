<template>
  <div ref="wrap" class="hist-band">
    <canvas ref="canvas"></canvas>
    <div v-if="means" class="means">
      μ R{{ means.r }} G{{ means.g }} B{{ means.b }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'imgStats',
  props: {
    imgStats: { type: Object, default: () => ({}) },
  },
  data() {
    return {
      cssW: 0,
      cssH: 140,
      ro: null,
    }
  },
  computed: {
    means() {
      const s = (this.imgStats && this.imgStats.spectrum) || {}
      if (s.mean_r == null) return null
      return {
        r: Number(s.mean_r).toFixed(0),
        g: Number(s.mean_g).toFixed(0),
        b: Number(s.mean_b).toFixed(0),
      }
    },
  },
  watch: {
    imgStats: {
      deep: true,
      handler() {
        this.draw()
      },
    },
  },
  mounted() {
    this.ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const w = Math.max(1, Math.floor(entry.contentRect.width))
      const h = Math.max(1, Math.floor(entry.contentRect.height))
      if (w === this.cssW && h === this.cssH) return
      this.cssW = w
      this.cssH = h
      this.draw()
    })
    this.ro.observe(this.$refs.wrap)
    this.draw()
  },
  beforeUnmount() {
    if (this.ro) {
      this.ro.disconnect()
      this.ro = null
    }
  },
  methods: {
    histChannels() {
      const stats = this.imgStats || {}
      const spectrum = stats.spectrum || {}
      if (
        Array.isArray(spectrum.hist_r) &&
        Array.isArray(spectrum.hist_g) &&
        Array.isArray(spectrum.hist_b)
      ) {
        return {
          r: spectrum.hist_r,
          g: spectrum.hist_g,
          b: spectrum.hist_b,
        }
      }
      // Fallback: legacy hub histData (already log-scaled)
      if (Array.isArray(stats.histData) && stats.histData.length >= 3) {
        return {
          r: stats.histData[0] || [],
          g: stats.histData[1] || [],
          b: stats.histData[2] || [],
          alreadyLog: true,
        }
      }
      return { r: [], g: [], b: [], alreadyLog: false }
    },
    draw() {
      const canvas = this.$refs.canvas
      const wrap = this.$refs.wrap
      if (!canvas || !wrap) return

      const dpr = window.devicePixelRatio || 1
      const cssW = Math.max(1, this.cssW || wrap.clientWidth || 1)
      const cssH = Math.max(1, this.cssH || wrap.clientHeight || 140)
      canvas.width = Math.floor(cssW * dpr)
      canvas.height = Math.floor(cssH * dpr)
      canvas.style.width = cssW + 'px'
      canvas.style.height = cssH + 'px'

      const ctx = canvas.getContext('2d')
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, cssW, cssH)

      // mid / clip guides
      ctx.strokeStyle = 'rgba(199,34,28,0.25)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(cssW * 0.5, 0)
      ctx.lineTo(cssW * 0.5, cssH)
      ctx.stroke()

      const ch = this.histChannels()
      const useLog = !ch.alreadyLog
      this.drawSeries(ctx, ch.b, 'rgba(68,136,255,0.35)', cssW, cssH, useLog)
      this.drawSeries(ctx, ch.g, 'rgba(68,255,136,0.35)', cssW, cssH, useLog)
      this.drawSeries(ctx, ch.r, 'rgba(255,68,68,0.4)', cssW, cssH, useLog)
    },
    drawSeries(ctx, values, color, width, height, useLog) {
      if (!Array.isArray(values) || values.length === 0) return
      const n = values.length
      const ys = new Array(n)
      let max = 0
      for (let i = 0; i < n; i++) {
        const raw = Number(values[i]) || 0
        const y = useLog ? Math.log10(1 + raw) : raw
        ys[i] = y
        if (y > max) max = y
      }
      if (max <= 0) max = 1

      ctx.beginPath()
      ctx.strokeStyle = color
      ctx.globalAlpha = 1
      ctx.lineWidth = 1.25
      for (let i = 0; i < n; i++) {
        const x = (i / Math.max(1, n - 1)) * (width - 1)
        const y = height - 2 - (ys[i] / max) * (height - 4)
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()
    },
  },
}
</script>

<style scoped>
.hist-band {
  position: relative;
  width: 100%;
  height: 140px;
  min-height: 140px;
  box-sizing: border-box;
  background: transparent;
}
canvas {
  display: block;
  width: 100%;
  height: 100%;
  background: transparent;
}
.means {
  position: absolute;
  top: 4px;
  right: 8px;
  font-family: monospace, sans-serif;
  font-size: 11px;
  color: var(--fg, #c7221c);
  text-shadow: 0 0 4px #000, 0 1px 2px #000;
  pointer-events: none;
}
</style>
