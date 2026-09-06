<template>
  <div class="viewwrap" ref="wrap">
    <img
      ref="img"
      class="viewwin"
      alt="camimg"
      :src="imgsrc()"
      :class="{ place: placeLock }"
      @click="imgClicked"
      @load="syncOverlay"
    />
    <svg
      v-if="trackEnabled && overlayBox"
      class="track-svg"
      :style="overlayBox"
      :viewBox="viewBox"
      preserveAspectRatio="none"
    >
      <rect
        :x="boxRect.x"
        :y="boxRect.y"
        :width="boxRect.w"
        :height="boxRect.h"
        class="lock-box"
      />
      <line
        :x1="cx"
        :y1="cy"
        :x2="ascTip[0]"
        :y2="ascTip[1]"
        class="axis-asc"
      />
      <line
        :x1="cx"
        :y1="cy"
        :x2="decTip[0]"
        :y2="decTip[1]"
        class="axis-dec"
      />
    </svg>
    <div v-if="showCrop && cropSrc" class="crop-inset">
      <img :src="cropSrc" alt="guide crop" />
      <span
        v-if="cropMark"
        class="crop-mark"
        :style="{ left: cropMark.x, top: cropMark.y }"
      />
    </div>
  </div>
</template>

<script>
import {
  locatorPreviewXy,
  previewXyToFullSensor,
  imageContentRect,
  clientPointToPreviewPx,
  overlayPercent,
  axisUnits,
  lockBoxPreviewPx,
} from '../ws/trackOverlay.js'

export default {
  name: 'imgDisplay',
  props: {
    imgData: { type: String, default: '' },
    imgProps: { type: Object, default: () => ({}) },
    track: { type: Object, default: () => ({}) },
    placeLock: { type: Boolean, default: false },
    cropJpeg: { type: String, default: '' },
    guideInfo: { type: Object, default: null },
  },
  emits: ['preview-click'],
  data() {
    return {
      overlayPct: null,
      previewWh: [2, 2],
    }
  },
  computed: {
    trackEnabled() {
      return Boolean(this.track && this.track.track_enabled)
    },
    showCrop() {
      return Boolean(this.track && this.track.guide_show_crop)
    },
    cropSrc() {
      if (!this.cropJpeg) return ''
      return 'data:image/jpeg;base64,' + this.cropJpeg
    },
    scalerCrop() {
      const used = this.usedSettings
      return used && used.scaler_crop != null ? used.scaler_crop : null
    },
    usedSettings() {
      const used = this.imgProps && this.imgProps.usedParams
      return used && used.settings && typeof used.settings === 'object'
        ? used.settings
        : this.track
    },
    overlayBox() {
      if (!this.overlayPct) return null
      const p = this.overlayPct
      return {
        left: p.left + '%',
        top: p.top + '%',
        width: p.width + '%',
        height: p.height + '%',
      }
    },
    viewBox() {
      return `0 0 ${this.previewWh[0]} ${this.previewWh[1]}`
    },
    lockPreview() {
      return locatorPreviewXy(
        this.track.track_x,
        this.track.track_y,
        this.previewWh,
        this.scalerCrop
      )
    },
    cx() {
      return this.lockPreview[0]
    },
    cy() {
      return this.lockPreview[1]
    },
    boxRect() {
      const [bw, bh] = lockBoxPreviewPx(
        this.track.track_roi,
        this.previewWh,
        this.usedSettings
      )
      return {
        x: this.cx - bw / 2,
        y: this.cy - bh / 2,
        w: bw,
        h: bh,
      }
    },
    arrowLen() {
      return Math.max(18, Math.min(this.previewWh[0], this.previewWh[1]) * 0.08)
    },
    ascTip() {
      const u = axisUnits(
        this.track.track_theta_deg,
        this.track.track_flip_asc,
        this.track.track_flip_dec
      )
      return [this.cx + u.asc[0] * this.arrowLen, this.cy + u.asc[1] * this.arrowLen]
    },
    decTip() {
      const u = axisUnits(
        this.track.track_theta_deg,
        this.track.track_flip_asc,
        this.track.track_flip_dec
      )
      return [this.cx + u.dec[0] * this.arrowLen, this.cy + u.dec[1] * this.arrowLen]
    },
    cropMark() {
      const g = this.guideInfo
      if (!g || g.u == null || g.v == null) return null
      const size = Math.max(1, Number(this.track.track_roi) || 32) * 2
      return {
        x: `${(Number(g.u) / size) * 100}%`,
        y: `${(Number(g.v) / size) * 100}%`,
      }
    },
  },
  watch: {
    imgData() {
      this.$nextTick(() => this.syncOverlay())
    },
    track: {
      deep: true,
      handler() {
        this.$nextTick(() => this.syncOverlay())
      },
    },
  },
  mounted() {
    this._ro = new ResizeObserver(() => this.syncOverlay())
    if (this.$refs.wrap) this._ro.observe(this.$refs.wrap)
    if (this.$refs.img) this._ro.observe(this.$refs.img)
  },
  beforeUnmount() {
    if (this._ro) this._ro.disconnect()
  },
  methods: {
    imgsrc() {
      if (!this.imgData) return ''
      return 'data:image/jpeg;base64,' + this.imgData
    },
    syncOverlay() {
      const img = this.$refs.img
      const wrap = this.$refs.wrap
      if (!img || !wrap || !img.naturalWidth) {
        this.overlayPct = null
        return
      }
      this.previewWh = [img.naturalWidth, img.naturalHeight]
      const imgRect = img.getBoundingClientRect()
      const wrapRect = wrap.getBoundingClientRect()
      const content = imageContentRect(imgRect, img.naturalWidth, img.naturalHeight)
      this.overlayPct = overlayPercent(content, wrapRect)
    },
    imgClicked(evt) {
      if (!this.placeLock) return
      const img = this.$refs.img
      if (!img || !img.naturalWidth) return
      const content = imageContentRect(
        img.getBoundingClientRect(),
        img.naturalWidth,
        img.naturalHeight
      )
      const hit = clientPointToPreviewPx(evt.clientX, evt.clientY, content)
      if (!hit) return
      const [nx, ny] = previewXyToFullSensor(
        hit.px,
        hit.py,
        [img.naturalWidth, img.naturalHeight],
        this.scalerCrop
      )
      this.$emit('preview-click', { x: nx, y: ny })
    },
  },
}
</script>

<style scoped>
.viewwrap {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
}
.viewwin {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border: 1px solid #a7021c;
  background: #000;
}
.viewwin.place {
  cursor: crosshair;
}
.track-svg {
  position: absolute;
  pointer-events: none;
  overflow: visible;
}
.lock-box {
  fill: none;
  stroke: #3ec6ff;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}
.axis-asc {
  stroke: #ffb000;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}
.axis-dec {
  stroke: #6dff8a;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}
.crop-inset {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 128px;
  border: 1px solid #3ec6ff;
  background: #000;
  pointer-events: none;
}
.crop-inset img {
  display: block;
  width: 100%;
  height: auto;
  image-rendering: pixelated;
}
.crop-mark {
  position: absolute;
  width: 8px;
  height: 8px;
  margin: -4px 0 0 -4px;
  border: 1px solid #fff;
  border-radius: 50%;
  box-sizing: border-box;
}
</style>
