<template>
  <div id="app">
    <div class="shell">
      <header class="toolbar">
        <div class="conn">
          <label class="conn-status" v-if="wsconnected">connected</label>
          <label class="conn-status" v-else>____</label>
          <button class="conn-btn" type="button" @click="makeConnection()">
            connect
          </button>
          <input class="conn-ip" v-model="wsip" />
        </div>
        <button type="button" @click="onshowsettings()">camera</button>
        <button type="button" @click="onshowmotorstats()">motors</button>
        <div class="toolbar-end">
          <memstats :memStats="diskUsage" />
        </div>
      </header>

      <section class="stage">
        <div class="preview">
          <imgDisplay v-if="wsconnected" :imgProps="{}" :imgData="imgData" />
        </div>

        <div class="hudScroll">
          <div class="overlays">
            <div v-show="showMotorstats">
              <stepperControl
                :slidestyle="slidestyle"
                :motorStats="motorStats"
                @newMotorParams="newMotorParams"
              />
            </div>

            <div v-show="showSettings" class="settings-stack">
              <div class="cam-inline">
                <imgStats :imgStats="imgStats" />
                <camStats :camStats="camStats" />
                <imgProps :imgProps="imgProps" />
              </div>
              <captureOptions
                :slidestyle="slidestyle"
                @newParams="newParams"
                @newMotorParams="newMotorParams"
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import captureOptions from './components/captureOptions.vue'
import imgDisplay from './components/imgDisplay.vue'
import imgProps from './components/imgProps.vue'
import imgStats from './components/imgStats.vue'
import memstats from './components/memoryStats.vue'
import camStats from './components/cameraStats.vue'
import stepperControl from './components/stepperControl.vue'
import {
  buildParamsMessage,
  buildCtlParamsMessage,
  parseInbound,
  INBOUND_TYPES,
} from './ws/messages.js'

const STATS_CAP = 100
const WSIP_STORAGE_KEY = 'astroscop.wsip'

function loadStoredWsip() {
  try {
    const stored = localStorage.getItem(WSIP_STORAGE_KEY)
    if (stored && stored.trim()) return stored.trim()
  } catch {
    /* ignore */
  }
  return 'localhost'
}

export default {
  name: 'App',
  components: {
    captureOptions,
    imgDisplay,
    imgProps,
    imgStats,
    memstats,
    camStats,
    stepperControl,
  },
  data() {
    return {
      wsconnected: false,
      wsip: loadStoredWsip(),
      connection: null,
      imgData: '',
      imgProps: {},
      imgStats: {},
      showSettings: false,
      showMotorstats: false,
      diskUsage: [],
      slidestyle: {
        backgroundColor: '#c7221c',
      },
      camStats: [],
      motorStats: [],
    }
  },
  methods: {
    onmessage(msg) {
      const parsed = parseInbound(msg.data)
      if (!parsed) {
        console.warn('invalid inbound message')
        return
      }
      const { msgtype, data, raw } = parsed
      switch (msgtype) {
        case INBOUND_TYPES.imgData:
          this.imgData = data
          break
        case INBOUND_TYPES.imgProps:
          this.imgProps = data || {}
          break
        case INBOUND_TYPES.imgStats:
          this.imgStats = data || {}
          break
        case INBOUND_TYPES.sysInfo:
          this.diskUsage = data || []
          break
        case INBOUND_TYPES.motorInfo:
          while (this.motorStats.length >= STATS_CAP) {
            this.motorStats.shift()
          }
          this.motorStats.push(raw)
          break
        case INBOUND_TYPES.camTiming:
          while (this.camStats.length >= STATS_CAP) {
            this.camStats.shift()
          }
          this.camStats.push(raw)
          break
        default:
          console.log('got message', msgtype, raw)
      }
    },
    onopen() {
      this.wsconnected = true
      try {
        localStorage.setItem(WSIP_STORAGE_KEY, this.wsip.trim())
      } catch {
        /* ignore */
      }
    },
    onclose(info) {
      console.log('onClose', info)
      this.wsconnected = false
    },
    newParams(params) {
      if (!this.wsconnected || !this.connection) return
      this.connection.send(JSON.stringify(buildParamsMessage(params)))
    },
    newMotorParams(params) {
      if (!this.wsconnected || !this.connection) return
      this.connection.send(JSON.stringify(buildCtlParamsMessage(params)))
    },
    makeConnection() {
      if (this.connection) {
        try {
          this.connection.close()
        } catch {
          /* ignore */
        }
      }
      this.connection = new WebSocket('ws://' + this.wsip + ':8765')
      this.connection.onmessage = this.onmessage
      this.connection.onopen = this.onopen
      this.connection.onclose = this.onclose
    },
    onshowmotorstats() {
      this.showMotorstats = !this.showMotorstats
    },
    onshowsettings() {
      this.showSettings = !this.showSettings
    },
  },
  beforeUnmount() {
    if (this.connection) {
      try {
        this.connection.close()
      } catch {
        /* ignore */
      }
    }
  },
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--fg, #c7221c);
  background: var(--bg, #050505);
  min-height: 100vh;
  text-align: center;
}

.shell {
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100vh;
  height: 100vh;
  overflow: hidden;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--bg, #050505);
  border-bottom: 1px solid var(--border, #7a1a16);
  z-index: 3;
}

.conn {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-right: 4px;
}

.conn-status {
  font-size: 11px;
  min-width: 4.5em;
  text-align: left;
}

.conn-btn {
  font-size: 11px;
  padding: 1px 6px;
  line-height: 1.3;
}

.conn-ip {
  font-size: 11px;
  width: 9em;
  padding: 1px 4px;
}

.toolbar-end {
  margin-left: auto;
  min-width: 0;
}

.stage {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: #000;
}

.preview {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.hudScroll {
  position: relative;
  z-index: 2;
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  pointer-events: none;
  background: transparent;
}

.overlays {
  position: relative;
  z-index: 2;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 6px;
  padding: 6px 0;
  box-sizing: border-box;
  pointer-events: none;
  background: transparent;
}

.overlays > * {
  pointer-events: auto;
  flex: 0 0 auto;
}

.settings-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 8px;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
}

.cam-inline {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  background: transparent;
  border: 1px solid var(--border);
  text-align: left;
}

.cam-inline .hist-band + .kpi-strip,
.cam-inline .kpi-strip + .kpi-strip {
  border-top: 1px solid var(--border);
}

.panel {
  box-sizing: border-box;
  min-width: 0;
  height: auto;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
  color: var(--fg, #c7221c);
}

.panelTitle {
  font-size: 12px;
  margin-bottom: 6px;
  color: var(--fg-dim, #8a2a26);
  text-transform: lowercase;
}

button {
  color: var(--fg, #c7221c);
  background: #000;
  border: 1px solid var(--border, #7a1a16);
  font-size: 16px;
  cursor: pointer;
}

input {
  color: var(--fg, #c7221c);
  background: #000;
  border: 1px solid var(--border, #7a1a16);
}
</style>
