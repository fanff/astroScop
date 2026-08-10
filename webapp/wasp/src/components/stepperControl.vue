<template>
  <div class="motor">
    <div class="panel motoropt">
      <div class="arm-row">
        <label class="arm">
          <input type="checkbox" id="motor-arm" v-model="checked" />
          Arm motor control
        </label>
        <div class="telem" :title="telemTitle">
          <span>ASC {{ fmtDeg(info.newascDeg) }}° s{{ fmt(info.ascStep) }}</span>
          <span class="sep">·</span>
          <span>DEC {{ fmtDeg(info.newdecDeg) }}° s{{ fmt(info.decStep) }}</span>
        </div>
      </div>

      <div class="axis">
        <div class="slider-meta">
          <span class="axisName">ASC</span>
          <span class="val">{{ readout(motorAscSpd) }}</span>
        </div>
        <div class="axis-controls">
          <select
            :value="spdRangeAsc"
            :disabled="!checked"
            @change="changeSpdRange('asc', $event.target.value)"
          >
            <option v-for="option in spdRangeKeys" :key="'asc-' + option">
              {{ option }}
            </option>
          </select>
          <input
            class="speed-num"
            type="number"
            v-model.number="motorAscSpd"
            :disabled="!checked"
            :min="rangeAsc.min"
            :max="rangeAsc.max"
            :step="rangeAsc.step"
          />
          <button type="button" :disabled="!checked" @click="nudge('asc', -1)">
            −
          </button>
          <button type="button" :disabled="!checked" @click="nudge('asc', 1)">
            +
          </button>
          <button type="button" :disabled="!checked" @click="setSidereal">
            sidereal
          </button>
          <button type="button" :disabled="!checked" @click="motorAscSpd = 0">
            stop
          </button>
        </div>
        <input
          type="range"
          :key="'asc-slider-' + spdRangeAsc"
          v-model.number="motorAscSpd"
          :disabled="!checked"
          :min="rangeAsc.min"
          :max="rangeAsc.max"
          :step="rangeAsc.step"
        />
        <div class="scale">
          <span>{{ rangeAsc.min }}</span>
          <span>0</span>
          <span>{{ rangeAsc.max }}</span>
        </div>
      </div>

      <div class="axis">
        <div class="slider-meta">
          <span class="axisName">DEC</span>
          <span class="val">{{ readout(motorDecSpd) }}</span>
        </div>
        <div class="axis-controls">
          <select
            :value="spdRangeDec"
            :disabled="!checked"
            @change="changeSpdRange('dec', $event.target.value)"
          >
            <option v-for="option in spdRangeKeys" :key="'dec-' + option">
              {{ option }}
            </option>
          </select>
          <input
            class="speed-num"
            type="number"
            v-model.number="motorDecSpd"
            :disabled="!checked"
            :min="rangeDec.min"
            :max="rangeDec.max"
            :step="rangeDec.step"
          />
          <button type="button" :disabled="!checked" @click="nudge('dec', -1)">
            −
          </button>
          <button type="button" :disabled="!checked" @click="nudge('dec', 1)">
            +
          </button>
          <button type="button" :disabled="!checked" @click="motorDecSpd = 0">
            stop
          </button>
        </div>
        <input
          type="range"
          :key="'dec-slider-' + spdRangeDec"
          v-model.number="motorDecSpd"
          :disabled="!checked"
          :min="rangeDec.min"
          :max="rangeDec.max"
          :step="rangeDec.step"
        />
        <div class="scale">
          <span>{{ rangeDec.min }}</span>
          <span>0</span>
          <span>{{ rangeDec.max }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/** Sidereal = 15.15 STEP/s → step_us = round(1e6/15.15) = 66007. */
const SIDEREAL_ABS = 15.15

const SPD_RANGES = {
  slow: { min: -25, max: 25, step: 0.05 },
  medium: { min: -100, max: 100, step: 0.1 },
  fast: { min: -500, max: 500, step: 1 },
  superfast: { min: -3000, max: 3000, step: 10 },
}

export default {
  name: 'stepperControl',
  props: {
    slidestyle: {
      type: Object,
      default: () => ({ backgroundColor: '#c7221c' }),
    },
    motorStats: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['newMotorParams'],
  data() {
    return {
      checked: false,
      spdRangeAsc: 'slow',
      spdRangeDec: 'slow',
      motorAscSpd: 0,
      motorDecSpd: 0,
      spdRangesDict: SPD_RANGES,
      siderealSpeed: -SIDEREAL_ABS,
    }
  },
  computed: {
    spdRangeKeys() {
      return Object.keys(this.spdRangesDict)
    },
    rangeAsc() {
      return this.spdRangesDict[this.spdRangeAsc]
    },
    rangeDec() {
      return this.spdRangesDict[this.spdRangeDec]
    },
    info() {
      if (!this.motorStats.length) return {}
      const last = this.motorStats[this.motorStats.length - 1]
      return last.data || last || {}
    },
    telemTitle() {
      const d = this.info
      if (!Object.keys(d).length) return 'waiting for motorInfo…'
      const asc = `ASC en=${d.ascEn ?? '?'} dir=${d.ascDir ?? '?'} ${d.ascStepUs ?? '—'}µs`
      const dec = `DEC en=${d.decEn ?? '?'} dir=${d.decDir ?? '?'} ${d.decStepUs ?? '—'}µs`
      return `${asc} · ${dec}`
    },
  },
  watch: {
    motorAscSpd(newSpeed) {
      if (this.checked && Number.isFinite(newSpeed)) {
        this.pushMotorParams({ k: 'ASC', v: Number(newSpeed) })
      }
    },
    motorDecSpd(newSpeed) {
      if (this.checked && Number.isFinite(newSpeed)) {
        this.pushMotorParams({ k: 'DEC', v: Number(newSpeed) })
      }
    },
  },
  methods: {
    readout(speed) {
      const v = Number(speed)
      if (!Number.isFinite(v) || v === 0) return '0 (stop)'
      const dir = v > 0 ? 'dir=0' : 'dir=1'
      return `${v.toFixed(2)} STEP/s · ${dir}`
    },
    fmt(v) {
      if (v === undefined || v === null) return '—'
      return String(v)
    },
    fmtDeg(v) {
      if (v === undefined || v === null || Number.isNaN(Number(v))) return '—'
      return Number(v).toFixed(3)
    },
    axisState(axis) {
      if (axis === 'dec') {
        return {
          speedKey: 'motorDecSpd',
          rangeKey: 'spdRangeDec',
          range: this.rangeDec,
        }
      }
      return {
        speedKey: 'motorAscSpd',
        rangeKey: 'spdRangeAsc',
        range: this.rangeAsc,
      }
    },
    clampValue(v, { min, max, step }) {
      let x = Number(v)
      if (!Number.isFinite(x)) x = 0
      if (x < min) x = min
      if (x > max) x = max
      // Snap relative to min to avoid float drift with fractional steps.
      const snapped = min + Math.round((x - min) / step) * step
      if (snapped < min) return min
      if (snapped > max) return max
      return Object.is(snapped, -0) ? 0 : Number(snapped.toFixed(6))
    },
    changeSpdRange(axis, mode) {
      const { speedKey, rangeKey } = this.axisState(axis)
      if (this[rangeKey] === mode) return
      // Capture before the range input can rewrite the value when min/max shrink.
      const prev = Number(this[speedKey])
      const next = this.clampValue(prev, this.spdRangesDict[mode])
      this[rangeKey] = mode
      this[speedKey] = next
    },
    nudge(axis, dir) {
      const { speedKey, range } = this.axisState(axis)
      this[speedKey] = this.clampValue(Number(this[speedKey]) + dir * range.step, range)
    },
    setSidereal() {
      this.changeSpdRange('asc', 'slow')
      this.motorAscSpd = this.siderealSpeed
      if (this.checked) {
        this.pushMotorParams({ k: 'ASC_SIDEREAL', v: this.siderealSpeed })
      }
    },
    pushMotorParams(params) {
      this.$emit('newMotorParams', params)
    },
  },
}
</script>

<style scoped>
.motor {
  padding: 0 8px;
  box-sizing: border-box;
}
.panel {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: auto;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 10px 12px;
  text-align: left;
  color: var(--fg, #c7221c);
}
.arm-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  min-width: 0;
}
.arm {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  flex-shrink: 0;
}
.telem {
  font-family: monospace, sans-serif;
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  text-align: right;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.telem .sep {
  margin: 0 4px;
  opacity: 0.6;
}
.axis {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  min-width: 0;
}
.axis:last-child {
  margin-bottom: 0;
}
.slider-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.axisName {
  font-weight: 600;
  flex-shrink: 0;
}
.axis-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.speed-num {
  width: 6.5rem;
  font-family: monospace, sans-serif;
  font-size: 12px;
}
.axis input[type='range'] {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  display: block;
}
.scale {
  display: flex;
  justify-content: space-between;
  font-family: monospace, sans-serif;
  font-size: 10px;
  color: var(--fg-dim, #8a2a26);
}
.val {
  font-family: monospace, sans-serif;
  font-size: 11px;
  text-align: right;
  word-break: break-word;
}
button:disabled,
select:disabled,
input:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
