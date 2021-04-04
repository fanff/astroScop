<template>
  <div >
      <div v-for="ms in memStats" :key="ms.disk">
          {{ms.disk}} : {{ms.usedpct.toFixed(1)}} % of {{ms.total.toFixed(1)}} Gig
      </div>
  </div>
</template>

<script>
//import Vue from "vue"

export default {
  components: {
  },

  name: 'memstats',
  props: {
      memStats:Array
  },
  data () {
    return {

    }
  },
  watch:{
  },
  methods: {
  },
  mounted(){
  },
  beforeDestroy(){
    //this.client.end()
  }
  
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
