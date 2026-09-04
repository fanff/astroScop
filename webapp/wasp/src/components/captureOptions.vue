<template>
  <div class="capture">
    <div class="panel exposure">
      <div class="slider-stack">
        <div class="slider-row">
          <div class="slider-meta">
            <span class="slider-name">shutter</span>
            <span class="slider-val">{{ shutterLabel }}</span>
          </div>
          <input
            type="range"
            v-model.number="shutter_log"
            :min="0"
            :max="shutterLogSteps"
            step="1"
            @input="onShutterLogInput"
          />
          <div class="shutter-exact">
            <input
              type="number"
              v-model.number="shutter_us"
              :min="shutterUsMin"
              :max="shutterUsMax"
              step="1"
              @change="onShutterUsInput"
            />
            <span class="unit">µs</span>
            <span class="hint">log · 1 µs – 2 min</span>
          </div>
        </div>

        <div class="slider-row">
          <div class="slider-meta">
            <span class="slider-name">analog_gain</span>
            <span class="slider-val">{{ analog_gain.toFixed(2) }}</span>
          </div>
          <input
            type="range"
            v-model.number="analog_gain"
            min="0.1"
            max="64"
            step="0.05"
            @input="schedulePush"
          />
        </div>

        <div class="slider-row">
          <div class="slider-meta">
            <span class="slider-name">colour_gain_r</span>
            <span class="slider-val">{{ colour_gain_r.toFixed(2) }} · log</span>
          </div>
          <input
            type="range"
            v-model.number="colour_gain_r_log"
            :min="0"
            :max="colourGainLogSteps"
            step="1"
            @input="onColourRLogInput"
          />
        </div>

        <div class="slider-row">
          <div class="slider-meta">
            <span class="slider-name">colour_gain_b</span>
            <span class="slider-val">{{ colour_gain_b.toFixed(2) }} · log</span>
          </div>
          <input
            type="range"
            v-model.number="colour_gain_b_log"
            :min="0"
            :max="colourGainLogSteps"
            step="1"
            @input="onColourBLogInput"
          />
        </div>
      </div>
    </div>

    <div class="below">
      <div class="panel sensor">
        <label>capture mode</label>
        <select v-model="captureModeId" @change="pushParamsNow">
          <option
            v-for="m in captureModes"
            :key="m.id"
            :value="m.id"
          >
            {{ m.label }}
          </option>
        </select>
        <p class="hint">{{ captureModeHint }}</p>
        <p class="hint">
          Native sensor modes: crop 1332×990 (fastest), bin2x2 1080/1520,
          full 2160/3040. “RGB …” variants keep that sensor readout but
          downscale the RGB stream (reconfigure). Preview size is JPEG-only.
        </p>

        <label>preview scale (JPEG only)</label>
        <select v-model.number="preview_div" @change="pushParamsNow">
          <option
            v-for="d in previewScales"
            :key="d.div"
            :value="d.div"
          >
            {{ d.label }}
          </option>
        </select>
        <p class="hint">
          Downscales the capture RGB for bandwidth; aspect ratio is kept.
          Browser scales the JPEG back up to fill the stage.
        </p>

        <div class="slider-row">
          <div class="slider-meta">
            <span class="slider-name">max_emit_fps</span>
            <span class="slider-val">{{ max_emit_fps }}</span>
          </div>
          <input
            type="range"
            v-model.number="max_emit_fps"
            min="0.5"
            max="30"
            step="0.5"
            @input="schedulePush"
          />
        </div>
      </div>

      <div class="panel saveopt">
        <label>
          <input type="checkbox" v-model="save_enabled" @change="pushParamsNow" />
          save_enabled (Bayer .npy)
        </label>

        <label>save_root</label>
        <input type="text" v-model="save_root" @change="schedulePush" />

        <label>save_section</label>
        <select v-model="save_section" @change="pushParamsNow">
          <option v-for="s in saveSections" :key="s" :value="s">{{ s }}</option>
        </select>

        <label>save_subsection</label>
        <input type="text" v-model="save_subsection" @change="schedulePush" />
      </div>
    </div>

    <div class="panel locator">
      <label>
        <input
          type="checkbox"
          v-model="locator_enabled"
          @change="pushParamsNow"
        />
        locator (preview overlay)
      </label>
      <p class="hint">
        Marks the telescope pointing on the tracking camera. Position is
        relative to the full sensor, so capture mode / preview scale do not
        move it. Crop clamps the mark to the visible edge.
      </p>

      <div class="slider-row">
        <div class="slider-meta">
          <span class="slider-name">locator X</span>
          <span class="slider-val">{{ locatorXLabel }}</span>
        </div>
        <input
          type="range"
          v-model.number="locator_x_slider"
          :min="0"
          :max="locatorSliderSteps"
          step="1"
          :disabled="!locator_enabled"
          @input="onLocatorXSlider"
        />
      </div>

      <div class="slider-row">
        <div class="slider-meta">
          <span class="slider-name">locator Y</span>
          <span class="slider-val">{{ locatorYLabel }}</span>
        </div>
        <input
          type="range"
          v-model.number="locator_y_slider"
          :min="0"
          :max="locatorSliderSteps"
          step="1"
          :disabled="!locator_enabled"
          @input="onLocatorYSlider"
        />
      </div>

      <div class="nudge" :class="{ dim: !locator_enabled }">
        <button
          type="button"
          class="nudge-btn"
          :disabled="!locator_enabled"
          @click="nudgeLocator(0, -locatorStep)"
        >
          up
        </button>
        <div class="nudge-mid">
          <button
            type="button"
            class="nudge-btn"
            :disabled="!locator_enabled"
            @click="nudgeLocator(-locatorStep, 0)"
          >
            left
          </button>
          <button
            type="button"
            class="nudge-btn"
            :disabled="!locator_enabled"
            @click="nudgeLocator(locatorStep, 0)"
          >
            right
          </button>
        </div>
        <button
          type="button"
          class="nudge-btn"
          :disabled="!locator_enabled"
          @click="nudgeLocator(0, locatorStep)"
        >
          down
        </button>
      </div>

      <div class="slider-row">
        <div class="slider-meta">
          <span class="slider-name">locator size</span>
          <span class="slider-val">{{ locatorSizeLabel }}</span>
        </div>
        <input
          type="range"
          v-model.number="locator_size"
          :min="locatorSizeMin"
          :max="locatorSizeMax"
          step="0.05"
          :disabled="!locator_enabled"
          @input="onLocatorSizeInput"
        />
        <p class="hint">Circle radius vs the default mark. Smaller for higher optical zoom.</p>
      </div>
    </div>
  </div>
</template>

<script>
import {
  CAPTURE_MODES,
  PREVIEW_SCALES,
  SAVE_SECTIONS,
  SHUTTER_US_MIN,
  SHUTTER_US_MAX,
  SHUTTER_LOG_STEPS,
  COLOUR_GAIN_LOG_STEPS,
  defaultCameraSettings,
  toWireSettings,
  clampShutterUs,
  shutterUsToLogPos,
  shutterLogPosToUs,
  formatShutterUs,
  colourGainToLogPos,
  colourGainLogPosToGain,
  captureModeIdFromSettings,
  previewDivFromSettings,
  clampNorm,
  locatorToSlider,
  sliderToLocator,
  formatLocatorPct,
  formatLocatorSize,
  clampLocatorSize,
  LOCATOR_STEP,
  LOCATOR_SLIDER_STEPS,
  LOCATOR_SIZE_MIN,
  LOCATOR_SIZE_MAX,
} from '../ws/cameraSettings.js'

const PUSH_DEBOUNCE_MS = 200

export default {
  name: 'captureOptions',
  props: {
    slidestyle: {
      type: Object,
      default: () => ({ backgroundColor: '#c7221c' }),
    },
    /**
     * One-shot camera settings captured by App on connect.
     * Must NOT be the per-frame imgProps stream.
     */
    settingsSnapshot: {
      type: Object,
      default: null,
    },
    /** Monotonic id; increments once per connect when snapshot is taken. */
    settingsEpoch: {
      type: Number,
      default: 0,
    },
    wsconnected: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['newParams', 'newMotorParams'],
  data() {
    const defaults = defaultCameraSettings()
    const shutter_us = clampShutterUs(defaults.shutter_us)
    const defaultMode =
      CAPTURE_MODES.find(
        (m) =>
          m.sensor_preset === defaults.sensor_preset &&
          m.main_width == null &&
          m.main_height == null
      ) || CAPTURE_MODES[5]
    return {
      captureModes: CAPTURE_MODES,
      previewScales: PREVIEW_SCALES,
      saveSections: SAVE_SECTIONS,
      shutterUsMin: SHUTTER_US_MIN,
      shutterUsMax: SHUTTER_US_MAX,
      shutterLogSteps: SHUTTER_LOG_STEPS,
      colourGainLogSteps: COLOUR_GAIN_LOG_STEPS,
      captureModeId: defaultMode.id,
      shutter_us,
      shutter_log: shutterUsToLogPos(shutter_us),
      analog_gain: defaults.analog_gain,
      colour_gain_r: defaults.colour_gain_r,
      colour_gain_b: defaults.colour_gain_b,
      colour_gain_r_log: colourGainToLogPos(defaults.colour_gain_r),
      colour_gain_b_log: colourGainToLogPos(defaults.colour_gain_b),
      preview_div: defaults.preview_div,
      max_emit_fps: defaults.max_emit_fps,
      save_enabled: defaults.save_enabled,
      save_root: defaults.save_root,
      save_section: defaults.save_section,
      save_subsection: defaults.save_subsection,
      locator_enabled: defaults.locator_enabled,
      locator_x: defaults.locator_x,
      locator_y: defaults.locator_y,
      locator_x_slider: locatorToSlider(defaults.locator_x),
      locator_y_slider: locatorToSlider(defaults.locator_y),
      locator_size: defaults.locator_size,
      locatorStep: LOCATOR_STEP,
      locatorSliderSteps: LOCATOR_SLIDER_STEPS,
      locatorSizeMin: LOCATOR_SIZE_MIN,
      locatorSizeMax: LOCATOR_SIZE_MAX,
      scaler_crop: defaults.scaler_crop,
      // Do NOT prefix with _: Vue 3 does not proxy those on `this`.
      hydrated: false,
      appliedEpoch: 0,
      suppressPush: false,
      pushTimer: null,
    }
  },
  computed: {
    shutterLabel() {
      return `${formatShutterUs(this.shutter_us)} (${this.shutter_us} µs)`
    },
    activeCaptureMode() {
      return (
        this.captureModes.find((m) => m.id === this.captureModeId) ||
        this.captureModes[0]
      )
    },
    captureModeHint() {
      const m = this.activeCaptureMode
      const main =
        m.main_width != null
          ? `RGB ${m.main_width}×${m.main_height}`
          : 'RGB = sensor size'
      return `${m.sensor_preset} · ${main} · reopens camera (brief blackout)`
    },
    locatorXLabel() {
      return formatLocatorPct(this.locator_x)
    },
    locatorYLabel() {
      return formatLocatorPct(this.locator_y)
    },
    locatorSizeLabel() {
      return formatLocatorSize(this.locator_size)
    },
  },
  watch: {
    wsconnected(connected) {
      if (!connected) {
        this.hydrated = false
        this.appliedEpoch = 0
        this.suppressPush = false
        this.clearPushTimer()
      }
    },
    settingsEpoch(epoch) {
      this.applySnapshotIfNeeded(epoch)
    },
    settingsSnapshot: {
      immediate: true,
      handler() {
        this.applySnapshotIfNeeded(this.settingsEpoch)
      },
    },
  },
  beforeUnmount() {
    this.clearPushTimer()
  },
  methods: {
    applySnapshotIfNeeded(epoch) {
      if (!this.wsconnected) return
      if (!epoch || epoch === this.appliedEpoch) return
      const snap = this.settingsSnapshot
      if (!snap || typeof snap !== 'object') return

      this.appliedEpoch = epoch
      this.suppressPush = true
      this.clearPushTimer()
      this.applyRemoteSettings(snap)
      this.hydrated = true
      // Allow DOM to settle so programmatic select updates cannot push.
      this.$nextTick(() => {
        this.suppressPush = false
      })
    },
    applyRemoteSettings(raw) {
      const s = toWireSettings(raw)
      this.captureModeId = captureModeIdFromSettings(s)
      this.shutter_us = s.shutter_us
      this.shutter_log = shutterUsToLogPos(s.shutter_us)
      this.analog_gain = s.analog_gain
      this.colour_gain_r = s.colour_gain_r
      this.colour_gain_b = s.colour_gain_b
      this.colour_gain_r_log = colourGainToLogPos(s.colour_gain_r)
      this.colour_gain_b_log = colourGainToLogPos(s.colour_gain_b)
      this.preview_div = previewDivFromSettings(s)
      this.max_emit_fps = s.max_emit_fps
      this.save_enabled = s.save_enabled
      this.save_root = s.save_root
      this.save_section = s.save_section
      this.save_subsection = s.save_subsection
      this.locator_enabled = s.locator_enabled
      this.locator_x = s.locator_x
      this.locator_y = s.locator_y
      this.locator_x_slider = locatorToSlider(s.locator_x)
      this.locator_y_slider = locatorToSlider(s.locator_y)
      this.locator_size = s.locator_size
      this.scaler_crop = s.scaler_crop
    },
    onLocatorSizeInput() {
      this.locator_size = clampLocatorSize(this.locator_size)
      this.schedulePush()
    },
    onLocatorXSlider() {
      this.locator_x = sliderToLocator(this.locator_x_slider)
      this.schedulePush()
    },
    onLocatorYSlider() {
      this.locator_y = sliderToLocator(this.locator_y_slider)
      this.schedulePush()
    },
    nudgeLocator(dx, dy) {
      this.locator_x = clampNorm(this.locator_x + dx)
      this.locator_y = clampNorm(this.locator_y + dy)
      this.locator_x_slider = locatorToSlider(this.locator_x)
      this.locator_y_slider = locatorToSlider(this.locator_y)
      this.pushParamsNow()
    },
    onShutterLogInput() {
      this.shutter_us = shutterLogPosToUs(this.shutter_log)
      this.schedulePush()
    },
    onShutterUsInput() {
      const clamped = clampShutterUs(this.shutter_us)
      this.shutter_us = clamped
      this.shutter_log = shutterUsToLogPos(clamped)
      this.schedulePush()
    },
    onColourRLogInput() {
      this.colour_gain_r = colourGainLogPosToGain(this.colour_gain_r_log)
      this.schedulePush()
    },
    onColourBLogInput() {
      this.colour_gain_b = colourGainLogPosToGain(this.colour_gain_b_log)
      this.schedulePush()
    },
    configData() {
      const mode = this.activeCaptureMode
      return toWireSettings({
        sensor_preset: mode.sensor_preset,
        main_width: mode.main_width,
        main_height: mode.main_height,
        shutter_us: this.shutter_us,
        analog_gain: this.analog_gain,
        colour_gain_r: this.colour_gain_r,
        colour_gain_b: this.colour_gain_b,
        preview_div: this.preview_div,
        max_emit_fps: this.max_emit_fps,
        save_enabled: this.save_enabled,
        save_root: this.save_root,
        save_section: this.save_section,
        save_subsection: this.save_subsection,
        save_format: this.save_enabled ? 'npy' : 'none',
        include_raw: true,
        science_neutral: true,
        locator_enabled: this.locator_enabled,
        locator_x: this.locator_x,
        locator_y: this.locator_y,
        locator_size: this.locator_size,
        scaler_crop: this.scaler_crop,
      })
    },
    clearPushTimer() {
      if (this.pushTimer != null) {
        clearTimeout(this.pushTimer)
        this.pushTimer = null
      }
    },
    canPush() {
      return this.wsconnected && this.hydrated && !this.suppressPush
    },
    schedulePush() {
      if (!this.canPush()) return
      this.clearPushTimer()
      this.pushTimer = setTimeout(() => {
        this.pushTimer = null
        this.pushParams()
      }, PUSH_DEBOUNCE_MS)
    },
    pushParamsNow() {
      if (!this.canPush()) return
      this.clearPushTimer()
      this.pushParams()
    },
    pushParams() {
      if (!this.canPush()) return
      this.$emit('newParams', this.configData())
    },
  },
}
</script>

<style scoped>
.capture {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 0 8px;
}

.panel {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: auto;
  overflow: hidden;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 10px 12px;
  text-align: left;
  color: var(--fg, #c7221c);
}

.exposure {
  width: 100%;
}

.slider-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.slider-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  min-width: 0;
}

.slider-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
}

.slider-name {
  color: var(--fg-dim, #8a2a26);
}

.slider-val {
  font-family: monospace, sans-serif;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slider-row input[type='range'] {
  width: 100%;
  box-sizing: border-box;
  display: block;
}

.below {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
  width: 100%;
}

.below > .panel {
  height: auto;
  align-self: start;
}

label {
  display: block;
  margin-top: 8px;
  font-size: 13px;
  color: var(--fg, #c7221c);
}

.sensor > label:first-child,
.saveopt > label:first-child {
  margin-top: 0;
}

input[type='text'],
input[type='number'],
select {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin-top: 2px;
}

.hint {
  font-size: 11px;
  color: var(--fg-dim, #8a2a26);
  margin: 4px 0 0;
}

.shutter-exact {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  min-width: 0;
}

.shutter-exact input[type='number'] {
  width: 10rem;
  flex: 0 0 auto;
}

.shutter-exact .unit,
.shutter-exact .hint {
  margin: 0;
  white-space: nowrap;
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

@media (max-width: 720px) {
  .below {
    grid-template-columns: 1fr;
  }
}
</style>
