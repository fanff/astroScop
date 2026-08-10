<template>
  <div class="viewwrap">
    <img
      class="viewwin"
      alt="camimg"
      :src="imgsrc()"
      @click="imgClicked"
    />
  </div>
</template>

<script>
export default {
  name: 'imgDisplay',
  props: {
    imgData: { type: String, default: '' },
    imgStats: { type: Object, default: () => ({}) },
    imgProps: { type: Object, default: () => ({}) },
  },
  methods: {
    imgsrc() {
      if (!this.imgData) return ''
      return 'data:image/jpeg;base64,' + this.imgData
    },
    imgClicked(evt) {
      const pixx =
        (evt.pageX - evt.target.offsetLeft) / evt.target.width
      const pixy =
        (evt.pageY - evt.target.offsetTop) / evt.target.height
      console.log('clicked', pixx, pixy)
    },
  },
}
</script>

<style scoped>
.viewwrap {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
}
.viewwin {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  border: 1px solid #a7021c;
  background: #000;
}
</style>
