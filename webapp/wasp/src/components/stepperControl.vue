<template>
  <div class="motor">
    <div class="panel motoropt">
      <div class="arm-row">
        <label class="arm">
          <input type="checkbox" id="motor-arm" v-model="checked" />
          Arm motor control
        </label>
        <div
          class="link-status"
          :class="linkClass"
          :title="linkTitle"
        >
          <span class="link-dot" aria-hidden="true" />
          <span class="link-label">{{ linkLabel }}</span>
        </div>
        <!-- Telem updates ~5 Hz; keep it outside v-memo so native <select>
             for slow/medium/fast is not patched/closed on every motorInfo. -->
        <div class="telem" :title="telemTitle">
          <span>ASC {{ fmtDeg(info.newascDeg) }}° s{{ fmt(info.ascStep) }}</span>
          <span class="sep">·</span>
          <span>DEC {{ fmtDeg(info.newdecDeg) }}° s{{ fmt(info.decStep) }}</span>
        </div>
      </div>

      <div
        v-memo="[
          checked,
          controlsEnabled,
          spdRangeAsc,
          spdRangeDec,
          motorAscSpd,
          motorDecSpd,
        ]"
      >
        <div class="axis">
          <div class="slider-meta">
            <span class="axisName">ASC</span>
            <span class="val">{{ readout(motorAscSpd) }}</span>
          </div>
          <div class="axis-controls">
            <select
              :value="spdRangeAsc"
              :disabled="!controlsEnabled"
              @change="changeSpdRange('asc', $event.target.value)"
            >
              <option
                v-for="option in spdRangeKeys"
                :key="'asc-' + option"
                :value="option"
              >
                {{ option }}
              </option>
            </select>
            <input
              class="speed-num"
              type="number"
              v-model.number="motorAscSpd"
              :disabled="!controlsEnabled"
              :min="rangeAsc.min"
              :max="rangeAsc.max"
              :step="rangeAsc.step"
            />
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="nudge('asc', -1)"
            >
              −
            </button>
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="nudge('asc', 1)"
            >
              +
            </button>
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="setSidereal"
            >
              sidereal
            </button>
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="motorAscSpd = 0"
            >
              stop
            </button>
          </div>
          <input
            type="range"
            v-model.number="motorAscSpd"
            :disabled="!controlsEnabled"
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
              :disabled="!controlsEnabled"
              @change="changeSpdRange('dec', $event.target.value)"
            >
              <option
                v-for="option in spdRangeKeys"
                :key="'dec-' + option"
                :value="option"
              >
                {{ option }}
              </option>
            </select>
            <input
              class="speed-num"
              type="number"
              v-model.number="motorDecSpd"
              :disabled="!controlsEnabled"
              :min="rangeDec.min"
              :max="rangeDec.max"
              :step="rangeDec.step"
            />
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="nudge('dec', -1)"
            >
              −
            </button>
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="nudge('dec', 1)"
            >
              +
            </button>
            <button
              type="button"
              :disabled="!controlsEnabled"
              @click="motorDecSpd = 0"
            >
              stop
            </button>
          </div>
          <input
            type="range"
            v-model.number="motorDecSpd"
            :disabled="!controlsEnabled"
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
  </div>
</template>

<script>
/** Sidereal = 15.15 STEP/s → step_us = round(1e6/15.15) = 66007. */
const SIDEREAL_ABS = 15.15
/** Treat motorInfo as stale if no update within this window (ms). */
const LINK_STALE_MS = 2000

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
      nowMs: Date.now(),
      _tick: null,
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
    lastStat() {
      if (!this.motorStats.length) return null
      return this.motorStats[this.motorStats.length - 1]
    },
    info() {
      const last = this.lastStat
      if (!last) return {}
      return last.data || last || {}
    },
    linkFresh() {
      const last = this.lastStat
      if (!last || last._rxAt == null) return false
      return this.nowMs - last._rxAt < LINK_STALE_MS
    },
    boardConnected() {
      return Boolean(this.info.connected) && this.linkFresh
    },
    controlsEnabled() {
      return this.checked && this.boardConnected
    },
    linkLabel() {
      if (!this.linkFresh) {
        if (!this.lastStat) return 'No motor service'
        return 'Link stale'
      }
      if (this.info.connected) {
        return this.info.port ? `Connected (${this.info.port})` : 'Connected'
      }
      if (this.info.link === 'error') return 'Board error'
      if (this.info.link === 'searching') return 'Searching…'
      return 'No board'
    },
    linkClass() {
      if (!this.linkFresh) return 'is-down'
      if (this.info.connected) return 'is-up'
      if (this.info.link === 'searching') return 'is-search'
      return 'is-down'
    },
    linkTitle() {
      const parts = [this.linkLabel]
      if (this.info.error) parts.push(String(this.info.error))
      if (this.info.armed) parts.push('UI armed')
      return parts.join(' · ')
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
    checked(armed) {
      if (armed) {
        this.pushMotorParams({ k: 'MOTOR_ARM', v: 1 })
      } else {
        this.pushMotorParams({ k: 'MOTOR_DISARM', v: 0 })
      }
    },
    motorAscSpd(newSpeed) {
      if (this.controlsEnabled && Number.isFinite(newSpeed)) {
        this.pushMotorParams({ k: 'ASC', v: Number(newSpeed) })
      }
    },
    motorDecSpd(newSpeed) {
      if (this.controlsEnabled && Number.isFinite(newSpeed)) {
        this.pushMotorParams({ k: 'DEC', v: Number(newSpeed) })
      }
    },
  },
  mounted() {
    this._tick = setInterval(() => {
      this.nowMs = Date.now()
    }, 500)
  },
  beforeUnmount() {
    if (this._tick) clearInterval(this._tick)
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
      const prev = Number(this[speedKey])
      const next = this.clampValue(prev, this.spdRangesDict[mode])
      // Clamp speed *before* swapping min/max/step so the live <input type="range">
      // never sees an out-of-range value (browser would rewrite v-model mid-change).
      if (next !== prev) {
        this[speedKey] = next
      }
      this[rangeKey] = mode
    },
    nudge(axis, dir) {
      const { speedKey, range } = this.axisState(axis)
      this[speedKey] = this.clampValue(Number(this[speedKey]) + dir * range.step, range)
    },
    setSidereal() {
      this.changeSpdRange('asc', 'slow')
      this.motorAscSpd = this.siderealSpeed
      if (this.controlsEnabled) {
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
  flex-wrap: wrap;
}
.arm {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  flex-shrink: 0;
}
.link-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-family: monospace, sans-serif;
  flex-shrink: 0;
}
.link-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.link-status.is-up {
  color: #2a7a3a;
}
.link-status.is-search {
  color: #8a6a16;
}
.link-status.is-down {
  color: #8a2a26;
}
.telem {
  font-family: monospace, sans-serif;
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  text-align: right;
  min-width: 18em;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  margin-left: auto;
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
