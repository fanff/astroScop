<template>
  <div v-show="usedParamsSet" class="kpi-strip">
    <span class="kpi"
      >shutter {{ fmt(usedParams.shutter_us) }}/{{
        fmt(usedParams.requested_shutter_us)
      }}
      µs</span
    >
    <span class="kpi"
      >gain {{ fmtNum(usedParams.analog_gain) }}/{{
        fmtNum(usedParams.requested_analog_gain)
      }}</span
    >
    <span class="kpi"
      >R/B {{ fmtNum(usedParams.colour_gain_r) }}/{{
        fmtNum(usedParams.colour_gain_b)
      }}</span
    >
    <span class="kpi"
      >{{ settings.sensor_preset || usedParams.sensor_preset || '—' }}
      {{ usedParams.frame_width || '—' }}×{{ usedParams.frame_height || '—' }}</span
    >
    <span class="kpi"
      >disp {{ settings.display_width || '—' }}×{{
        settings.display_height || '—'
      }}</span
    >
    <span class="kpi"
      >save {{ usedParams.save_enabled ? 'on' : 'off' }}
      {{ usedParams.save_section || '' }}</span
    >
  </div>
</template>

<script>
export default {
  name: 'imgProps',
  props: {
    imgProps: { type: Object, default: () => ({}) },
  },
  data() {
    return {
      usedParamsSet: false,
      usedParams: {},
    }
  },
  computed: {
    settings() {
      return this.usedParams.settings || {}
    },
  },
  watch: {
    imgProps: {
      immediate: true,
      handler(newval) {
        const up = newval && newval.usedParams
        if (!up || typeof up !== 'object') {
          this.usedParams = {}
          this.usedParamsSet = false
          return
        }
        this.usedParams = up
        this.usedParamsSet = true
      },
    },
  },
  methods: {
    fmt(v) {
      if (v === undefined || v === null) return '—'
      if (Array.isArray(v)) return v.join(',')
      return String(v)
    },
    fmtNum(v) {
      if (v === undefined || v === null || Number.isNaN(Number(v))) return '—'
      return Number(v).toFixed(2)
    },
  },
}
</script>
