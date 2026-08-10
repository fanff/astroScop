<template>
  <div class="cam-stats kpi-strip">
    <span v-if="!hasData" class="kpi kpi-empty">waiting for camera timing…</span>
    <template v-else>
      <span class="kpi">queue {{ fmt(pending) }}/{{ fmt(slots) }}</span>
      <span class="kpi"
        >capture {{ fmtFps(stat.capture_fps) }} fps /
        {{ fmtMs(stat.frame_time_ms) }}</span
      >
      <span class="kpi"
        >publish {{ fmtFps(stat.science_publish_fps) }} fps / write
        {{ fmtFps(stat.science_write_fps) }} fps</span
      >
      <span class="kpi">fill in {{ fmtEta(stat.queue_fill_eta_s) }}</span>
      <span class="kpi">dropped {{ fmt(stat.science_dropped) }}</span>
      <span class="kpi">save {{ fmtSave(stat.save_enabled) }}</span>
    </template>
  </div>
</template>

<script>
export default {
  name: 'camStats',
  props: {
    camStats: { type: Array, default: () => [] },
  },
  computed: {
    hasData() {
      return this.camStats.length > 0
    },
    stat() {
      if (!this.camStats.length) return {}
      const last = this.camStats[this.camStats.length - 1]
      return last.data || last || {}
    },
    pending() {
      const s = this.stat
      if (s.science_pending != null) return s.science_pending
      return s.tosavecount
    },
    slots() {
      return this.stat.science_slots
    },
  },
  methods: {
    fmt(v) {
      if (v === undefined || v === null) return '—'
      return String(v)
    },
    fmtFps(v) {
      if (v === undefined || v === null || Number.isNaN(Number(v))) return '—'
      return Number(v).toFixed(1)
    },
    fmtMs(v) {
      if (v === undefined || v === null || Number.isNaN(Number(v))) return '—'
      return `${Number(v).toFixed(0)} ms`
    },
    fmtEta(v) {
      if (v === undefined || v === null) return '—'
      const n = Number(v)
      if (Number.isNaN(n)) return '—'
      if (n <= 0) return 'full'
      if (n >= 10) return `${Math.round(n)} s`
      return `${n.toFixed(1)} s`
    },
    fmtSave(v) {
      if (v === undefined || v === null) return '—'
      if (v === true || v === 1 || v === '1' || v === 'true') return 'on'
      if (v === false || v === 0 || v === '0' || v === 'false') return 'off'
      return String(v)
    },
  },
}
</script>
