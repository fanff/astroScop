<template>
    <div class="parent" >
 
        <div class="div1"> 
            <trend :data="bvals" :gradient="['#00F']" auto-draw :width="histW()" :height="histH()" ></trend>
        </div>
        <div class="div2"> 
            <trend :data="gvals" :gradient="['#0F0']" auto-draw :width="histW()" :height="histH()"></trend>
        </div>
        <div class="div3">
            <trend :data="rvals" :gradient="['#F00']" auto-draw :width="histW()" :height="histH()"></trend>
        </div>
    </div>
</template>

<script>
import Trend from "vuetrend"

export default {
  components: {
      Trend
  },

  name: 'imgStats',
  props: {

    imgStats: Object,
  },
  data () {
    return {
        bvals:[],
        gvals:[],
        rvals:[],

    }
  },
  watch:{
    imgStats:function(newval){
        //console.log("imgstats ",newval)
        this.bvals=newval["histData"][2]
        this.gvals=newval["histData"][1]
        this.rvals=newval["histData"][0]
            
        //this.vals.shift()
    }
  },
  methods: {
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


.parent {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: 1fr;
    grid-column-gap: 0px;
    grid-row-gap: 0px;
}

.div1 { grid-area: 1 / 1 / 2 / 2; }
.div2 { grid-area: 1 / 1 / 2 / 2; }
.div3 { grid-area: 1 / 1 / 2 / 2; }
</style>
