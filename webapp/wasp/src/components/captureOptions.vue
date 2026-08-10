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

        <label>preview size (JPEG only)</label>
        <select v-model="displayPreset" @change="pushParamsNow">
          <option
            v-for="d in displayPresets"
            :key="d.label"
            :value="d.label"
          >
            {{ d.label }}
          </option>
        </select>

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
  </div>
</template>

<script>
import {
  CAPTURE_MODES,
  DISPLAY_PRESETS,
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
  displayPresetFromSettings,
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
    const display =
      DISPLAY_PRESETS.find(
        (d) =>
          d.width === defaults.display_width &&
          d.height === defaults.display_height
      ) || DISPLAY_PRESETS[1]
    const defaultMode =
      CAPTURE_MODES.find(
        (m) =>
          m.sensor_preset === defaults.sensor_preset &&
          m.main_width == null &&
          m.main_height == null
      ) || CAPTURE_MODES[5]
    return {
      captureModes: CAPTURE_MODES,
      displayPresets: DISPLAY_PRESETS,
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
      displayPreset: display.label,
      max_emit_fps: defaults.max_emit_fps,
      save_enabled: defaults.save_enabled,
      save_root: defaults.save_root,
      save_section: defaults.save_section,
      save_subsection: defaults.save_subsection,
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
      this.displayPreset = displayPresetFromSettings(s)
      this.max_emit_fps = s.max_emit_fps
      this.save_enabled = s.save_enabled
      this.save_root = s.save_root
      this.save_section = s.save_section
      this.save_subsection = s.save_subsection
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
    currentDisplaySize() {
      return (
        this.displayPresets.find((d) => d.label === this.displayPreset) ||
        this.displayPresets[1]
      )
    },
    configData() {
      const disp = this.currentDisplaySize()
      const mode = this.activeCaptureMode
      return toWireSettings({
        sensor_preset: mode.sensor_preset,
        main_width: mode.main_width,
        main_height: mode.main_height,
        shutter_us: this.shutter_us,
        analog_gain: this.analog_gain,
        colour_gain_r: this.colour_gain_r,
        colour_gain_b: this.colour_gain_b,
        display_width: disp.width,
        display_height: disp.height,
        max_emit_fps: this.max_emit_fps,
        save_enabled: this.save_enabled,
        save_root: this.save_root,
        save_section: this.save_section,
        save_subsection: this.save_subsection,
        save_format: this.save_enabled ? 'npy' : 'none',
        include_raw: true,
        science_neutral: true,
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

@media (max-width: 720px) {
  .below {
    grid-template-columns: 1fr;
  }
}
</style>
