<template>
  <div >
Buffer Size = {{lastStat().imgbuffcount}}
  </div>
</template>

<script>
//import Vue from "vue"

export default {
  components: {
  },

  name: 'camStats',
  props: {
      camStats:Array
  },
  data () {
    return {

    }
  },
  watch:{
  },
  methods: {
      lastStat: function(){
        if(this.camStats.length>0){
            return this.camStats[this.camStats.length-1].data;
        }else{
            return {}
        }
      },
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
