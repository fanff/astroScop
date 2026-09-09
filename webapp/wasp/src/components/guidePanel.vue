<template>
  <div class="panel guide">
    <label>
      <input
        type="checkbox"
        :checked="settings.track_enabled"
        :disabled="disabled"
        @change="setField('track_enabled', $event.target.checked)"
      />
      tracking lock
    </label>
    <p class="hint">
      Second locator for autoguide (not the red composition mark). Mixer stays
      off until Guide enable (motors armed, Pico linked, star ok).
    </p>

    <label>
      <input
        type="checkbox"
        :checked="placeLock"
        :disabled="disabled || !settings.track_enabled"
        @change="$emit('update:placeLock', $event.target.checked)"
      />
      place lock (click preview)
    </label>

    <div class="slider-row">
      <div class="slider-meta">
        <span class="slider-name">lock X</span>
        <span class="slider-val">{{ xLabel }}</span>
      </div>
      <input
        type="range"
        :value="xSlider"
        :min="0"
        :max="locatorSliderSteps"
        step="1"
        :disabled="!settings.track_enabled || disabled"
        @input="onXSlider($event.target.value)"
      />
    </div>
    <div class="slider-row">
      <div class="slider-meta">
        <span class="slider-name">lock Y</span>
        <span class="slider-val">{{ yLabel }}</span>
      </div>
      <input
        type="range"
        :value="ySlider"
        :min="0"
        :max="locatorSliderSteps"
        step="1"
        :disabled="!settings.track_enabled || disabled"
        @input="onYSlider($event.target.value)"
      />
    </div>

    <div class="nudge" :class="{ dim: !settings.track_enabled }">
      <button type="button" class="nudge-btn" :disabled="lockOff" @click="nudge(0, -step)">
        up
      </button>
      <div class="nudge-mid">
        <button type="button" class="nudge-btn" :disabled="lockOff" @click="nudge(-step, 0)">
          left
        </button>
        <button type="button" class="nudge-btn" :disabled="lockOff" @click="nudge(step, 0)">
          right
        </button>
      </div>
      <button type="button" class="nudge-btn" :disabled="lockOff" @click="nudge(0, step)">
        down
      </button>
    </div>

    <div class="slider-row">
      <div class="slider-meta">
        <span class="slider-name">ROI half-size</span>
        <span class="slider-val">{{ settings.track_roi }} px</span>
      </div>
      <input
        type="range"
        :value="settings.track_roi"
        :min="roiMin"
        :max="roiMax"
        step="1"
        :disabled="lockOff"
        @input="setField('track_roi', Number($event.target.value))"
      />
    </div>

    <div class="slider-row">
      <div class="slider-meta">
        <span class="slider-name">stack N frames</span>
        <span class="slider-val">{{ settings.guide_stack_n }}</span>
      </div>
      <input
        type="range"
        :value="settings.guide_stack_n"
        :min="stackMin"
        :max="stackMax"
        step="1"
        :disabled="disabled"
        @input="setField('guide_stack_n', Number($event.target.value))"
      />
    </div>

    <div class="slider-row">
      <div class="slider-meta">
        <span class="slider-name">Kp (STEP/s / px)</span>
        <span class="slider-val">{{ fmt(settings.guide_kp, 3) }}</span>
      </div>
      <input
        type="range"
        :value="settings.guide_kp"
        :min="kpMin"
        :max="kpMax"
        step="0.01"
        :disabled="disabled"
        @input="setField('guide_kp', Number($event.target.value))"
      />
    </div>
    <div class="slider-row">
      <div class="slider-meta">
        <span class="slider-name">Ki (STEP/s / px / s)</span>
        <span class="slider-val">{{ fmt(settings.guide_ki, 3) }}</span>
      </div>
      <input
        type="range"
        :value="settings.guide_ki"
        :min="kiMin"
        :max="kiMax"
        step="0.001"
        :disabled="disabled"
        @input="setField('guide_ki', Number($event.target.value))"
      />
    </div>
    <p class="hint">If error hunts slowly, drop Ki (or raise Kp). Live — does not reset I.</p>

    <div class="axes">
      <button type="button" class="nudge-btn" :disabled="lockOff" @click="rotate90">
        rotate 90° (θ={{ settings.track_theta_deg }}°)
      </button>
      <label>
        <input
          type="checkbox"
          :checked="settings.track_flip_asc"
          :disabled="lockOff"
          @change="setField('track_flip_asc', $event.target.checked)"
        />
        flip ASC+
      </label>
      <label>
        <input
          type="checkbox"
          :checked="settings.track_flip_dec"
          :disabled="lockOff"
          @change="setField('track_flip_dec', $event.target.checked)"
        />
        flip DEC+
      </label>
      <p class="hint">Orange = ASC+, green = DEC+ on the overlay.</p>
    </div>

    <label>DEC (deg)</label>
    <input
      type="number"
      v-model="decDraft"
      min="-90"
      max="90"
      step="0.1"
      :disabled="disabled"
      @focus="decFocused = true"
      @blur="commitDec"
      @change="commitDec"
    />

    <label>focal length (mm)</label>
    <input
      type="number"
      v-model="fmmDraft"
      min="0"
      max="10000"
      step="1"
      :disabled="disabled"
      @focus="fmmFocused = true"
      @blur="commitFmm"
      @change="commitFmm"
    />

    <label>
      <input
        type="checkbox"
        :checked="mixerWanted"
        :disabled="!canEnable && !mixerWanted"
        @change="$emit('update:mixerWanted', $event.target.checked)"
      />
      guide enable (rate trims)
    </label>
    <p v-if="enableBlock" class="hint">{{ enableBlock }}</p>

    <label>
      <input
        type="checkbox"
        :checked="settings.guide_show_crop"
        :disabled="disabled"
        @change="setField('guide_show_crop', $event.target.checked)"
      />
      show work crop
    </label>

    <div class="readout" :class="{ lost: lostStar }">
      <div v-if="lostStar">lost star — mixer dropped to feedforward</div>
      <div>ok {{ info.ok ? 'yes' : 'no' }}{{ lostWhy }} · SNR {{ fmt(info.snr, 1) }}</div>
      <div>
        error {{ fmt(info.e_asc_arcsec, 2) }}″ / {{ fmt(info.e_dec_arcsec, 2) }}″
        · {{ fmt(info.e_asc_steps, 2) }} / {{ fmt(info.e_dec_steps, 2) }} STEP
      </div>
      <div>
        trim {{ fmt(info.dAsc, 3) }} / {{ fmt(info.dDec, 3) }} STEP/s
      </div>
      <div>
        native ff {{ fmt(motor.ffAsc, 2) }} / {{ fmt(motor.ffDec, 2) }} STEP/s
      </div>
      <div>
        applied {{ fmt(appliedAsc, 2) }} / {{ fmt(appliedDec, 2) }} STEP/s
        ·         mixer {{ motor.guideEnabled ? 'on' : 'off' }}
      </div>
      <div v-if="mixerWanted && !motor.guideEnabled" class="hint">
        Guide enable is on in the UI but the motor mixer is off — trim is not applied.
      </div>
      <div class="hint">
        worker f={{ fmt(info.focal_mm, 0) }} mm · δ={{ fmt(info.dec_deg, 1) }}°
        · bin {{ info.bin != null ? info.bin : '—' }}
        · stack {{ info.stack_n != null ? info.stack_n : settings.guide_stack_n }}
        · Kp {{ fmt(info.kp != null ? info.kp : settings.guide_kp, 3) }}
        · Ki {{ fmt(info.ki != null ? info.ki : settings.guide_ki, 3) }}
      </div>
      <p class="hint">Motor sliders are feedforward only; trim adds on top.</p>
      <p v-if="!guideInfo" class="hint">No guideInfo — is astroscop-guide running?</p>
    </div>
  </div>
</template>

<script>
import {
  clampNorm,
  locatorToSlider,
  sliderToLocator,
  formatLocatorPct,
  LOCATOR_STEP,
  LOCATOR_SLIDER_STEPS,
  TRACK_ROI_MIN,
  TRACK_ROI_MAX,
  GUIDE_STACK_MIN,
  GUIDE_STACK_MAX,
  GUIDE_KP_MIN,
  GUIDE_KP_MAX,
  GUIDE_KI_MIN,
  GUIDE_KI_MAX,
  clampTrackTheta,
  pickGuideSettings,
} from '../ws/cameraSettings.js'
import { guideEnableAllowed, guideEnableBlockReason } from '../ws/guideEnable.js'

export default {
  name: 'guidePanel',
  props: {
    settings: { type: Object, required: true },
    placeLock: { type: Boolean, default: false },
    mixerWanted: { type: Boolean, default: false },
    guideInfo: { type: Object, default: null },
    motorInfo: { type: Object, default: () => ({}) },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:settings', 'update:placeLock', 'update:mixerWanted'],
  data() {
    return {
      step: LOCATOR_STEP,
      locatorSliderSteps: LOCATOR_SLIDER_STEPS,
      roiMin: TRACK_ROI_MIN,
      roiMax: TRACK_ROI_MAX,
      stackMin: GUIDE_STACK_MIN,
      stackMax: GUIDE_STACK_MAX,
      kpMin: GUIDE_KP_MIN,
      kpMax: GUIDE_KP_MAX,
      kiMin: GUIDE_KI_MIN,
      kiMax: GUIDE_KI_MAX,
      decDraft: 0,
      fmmDraft: 18,
      decFocused: false,
      fmmFocused: false,
    }
  },
  computed: {
    lockOff() {
      return this.disabled || !this.settings.track_enabled
    },
    xSlider() {
      return locatorToSlider(this.settings.track_x)
    },
    ySlider() {
      return locatorToSlider(this.settings.track_y)
    },
    xLabel() {
      return formatLocatorPct(this.settings.track_x)
    },
    yLabel() {
      return formatLocatorPct(this.settings.track_y)
    },
    info() {
      return this.guideInfo || {}
    },
    lostWhy() {
      if (this.info.ok) return ''
      const r = this.info.reason
      return r ? ` (${r})` : ''
    },
    lostStar() {
      return Boolean(this.settings.track_enabled && this.guideInfo && this.guideInfo.ok === false)
    },
    motor() {
      return this.motorInfo || {}
    },
    appliedAsc() {
      const cmd = Number(this.motor.cmdAsc)
      if (Number.isFinite(cmd)) return cmd
      const ff = Number(this.motor.ffAsc)
      const d = this.motor.guideEnabled ? Number(this.motor.dAsc) : 0
      if (!Number.isFinite(ff)) return NaN
      return ff + (Number.isFinite(d) ? d : 0)
    },
    appliedDec() {
      const cmd = Number(this.motor.cmdDec)
      if (Number.isFinite(cmd)) return cmd
      const ff = Number(this.motor.ffDec)
      const d = this.motor.guideEnabled ? Number(this.motor.dDec) : 0
      if (!Number.isFinite(ff)) return NaN
      return ff + (Number.isFinite(d) ? d : 0)
    },
    canEnable() {
      return guideEnableAllowed({
        motor: this.motor,
        guide: this.guideInfo,
        settings: this.settings,
      })
    },
    enableBlock() {
      if (this.mixerWanted) return ''
      return guideEnableBlockReason({
        motor: this.motor,
        guide: this.guideInfo,
        settings: this.settings,
      })
    },
  },
  watch: {
    'settings.guide_dec_deg': {
      immediate: true,
      handler(v) {
        if (!this.decFocused) this.decDraft = v
      },
    },
    'settings.guide_focal_mm': {
      immediate: true,
      handler(v) {
        if (!this.fmmFocused) this.fmmDraft = v
      },
    },
  },
  methods: {
    emitPatch(patch) {
      this.$emit('update:settings', pickGuideSettings({ ...this.settings, ...patch }))
    },
    setField(key, value) {
      this.emitPatch({ [key]: value })
    },
    onXSlider(pos) {
      this.emitPatch({ track_x: sliderToLocator(pos) })
    },
    onYSlider(pos) {
      this.emitPatch({ track_y: sliderToLocator(pos) })
    },
    nudge(dx, dy) {
      this.emitPatch({
        track_x: clampNorm(this.settings.track_x + dx),
        track_y: clampNorm(this.settings.track_y + dy),
      })
    },
    rotate90() {
      this.emitPatch({
        track_theta_deg: clampTrackTheta(this.settings.track_theta_deg + 90),
      })
    },
    commitDec() {
      this.decFocused = false
      this.emitPatch({ guide_dec_deg: this.decDraft })
    },
    commitFmm() {
      this.fmmFocused = false
      this.emitPatch({ guide_focal_mm: this.fmmDraft })
    },
    fmt(v, digits) {
      const n = Number(v)
      if (!Number.isFinite(n)) return '—'
      return n.toFixed(digits)
    },
  },
}
</script>

<style scoped>
.panel {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 10px 12px;
  text-align: left;
  color: var(--fg, #c7221c);
}
.slider-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  margin-top: 8px;
}
.slider-meta {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.slider-name {
  color: var(--fg-dim, #8a2a26);
}
.slider-val {
  font-family: monospace, sans-serif;
}
.slider-row input[type='range'] {
  width: 100%;
}
label {
  display: block;
  margin-top: 8px;
  font-size: 13px;
}
label:first-child {
  margin-top: 0;
}
input[type='number'] {
  width: 100%;
  box-sizing: border-box;
  margin-top: 2px;
}
.hint {
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  margin: 4px 0 0;
}
.nudge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
}
.nudge.dim {
  opacity: 0.45;
}
.nudge-mid {
  display: flex;
  gap: 8px;
}
.nudge-btn {
  min-width: 4.2em;
  font-size: 13px;
  padding: 2px 8px;
}
.axes {
  margin-top: 8px;
}
.readout {
  margin-top: 10px;
  font-family: monospace, sans-serif;
  font-size: 12px;
  line-height: 1.4;
}
.readout.lost {
  color: #ffb000;
}
</style>
