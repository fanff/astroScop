<template>
  <div >
    <br/>
      motorInfo {{ motorStats.length }}
    <br/>

      {{ lastStat() }}
    <br/>
  </div>
</template>

<script>
//import Vue from "vue"

//import Trend from "vuetrend"
export default {
  components: {
      //Trend
  },

  name: 'motorStats',
  props: {
    motorStats:Array
  },
  data () {
    return {
        errvalues:[]
    }
  },
  watch:{
    motorStats:function(){
        //cmd 
        //err: 
        //mspd: 
        //rspd
        //this.errvalues = this.motorStats.map(function(h){return h.data.err})
        //console.log("motorStats ",this.motorStats)
    }
  },
  methods: {
      lastStat: function(){
        if(this.motorStats.length>0){

            return this.motorStats[this.motorStats.length-1].data;
        }else{

            return {}
        }
      },
      histW: function(){
        return 300;
      },
      histH: function(){
        return (this.histW()*9)/16.0
      }
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
