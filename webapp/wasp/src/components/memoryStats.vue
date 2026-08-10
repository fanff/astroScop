<template>
  <div class="mem-strip" :title="fullTitle">
    <span v-if="!rows.length" class="empty">sys…</span>
    <template v-else>
      <span v-for="(ms, i) in rows" :key="ms.disk" class="item" :title="detail(ms)">
        <template v-if="i"> · </template>{{ label(ms) }} {{ pct(ms) }}%
      </span>
    </template>
  </div>
</template>

<script>
export default {
  name: 'memstats',
  props: {
    memStats: { type: Array, default: () => [] },
  },
  computed: {
    rows() {
      return Array.isArray(this.memStats) ? this.memStats : []
    },
    fullTitle() {
      if (!this.rows.length) return 'waiting for sysInfo…'
      return this.rows.map((ms) => this.detail(ms)).join('\n')
    },
  },
  methods: {
    label(ms) {
      const d = String(ms.disk || '')
      if (d === 'cpu') return 'cpu'
      if (d === 'mem' || d === 'memory' || d === 'ram') return 'mem'
      if (d === '/' || d === 'root') return '/'
      return d.length > 8 ? d.slice(0, 8) : d
    },
    pct(ms) {
      return Number(ms.usedpct || 0).toFixed(0)
    },
    detail(ms) {
      const unit = ms.disk === 'cpu' ? '%' : ' GiB'
      return `${ms.disk}: ${Number(ms.used || 0).toFixed(1)} / ${Number(ms.total || 0).toFixed(1)}${unit} · free ${Number(ms.free || 0).toFixed(1)} (${this.pct(ms)}%)`
    },
  },
}
</script>

<style scoped>
.mem-strip {
  font-family: monospace, sans-serif;
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: min(42vw, 28rem);
  line-height: 1.2;
}
.item {
  color: var(--fg, #c7221c);
}
.empty {
  color: var(--fg-dim, #8a2a26);
}
</style>
