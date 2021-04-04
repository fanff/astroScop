<template>
  <div >
     <div v-show="usedParamsSet" class="parent">
         <div class="div0"> 
            <imgStats v-bind:imgStats="imgStats"></imgStats>
         </div> 
         <div class="div1">
             <ul>
                 <li>{{usedParams.triggerDateStr}}</li>
                 <li>isovalue: {{usedParams.isovalue}}</li>
                 <li>R/B:{{usedParams.redgain.toFixed(2)}} {{usedParams.bluegain.toFixed(2)}}</li>
                 <li>brt:{{usedParams.brightness}} sat:{{usedParams.saturation}}</li>
                 <li>expo:{{usedParams.exposure_compensation}} ctrst:{{usedParams.contrast}}</li>
                 <li>iso: {{usedParams.isovalue}} sharp :{{usedParams.sharpness}}</li>
                 <li>shutter: {{usedParams.shutterSpeed}}</li>
             </ul>
         </div>

         <div class="div2"> 
             <ul>
                 <li>shot: {{usedParams.shootresol.name}}</li>
                 <li>displ:{{usedParams.dispresol.name}}</li>
                 <li>expo_mode:{{usedParams.expomode}}</li>
                 <li>capture: {{usedParams.capture_format}}</li>
                 <li>save_format: {{usedParams.save_format}}</li>
                 <li>fdest: {{usedParams.fdest}}</li>
                 <li>filename: {{usedParams.fileNameExt}}</li>


             </ul>
         </div>
          <div class="div3"> 
             <ul>
<li>sensor_mode :{{usedParams.sensor_mode}} </li>
<li>video_denoise :{{usedParams.video_denoise}} </li>
<li>video_stabilization :{{usedParams.video_stabilization}} </li>
<li>zoom :{{usedParams.zoom}} </li>
<li>revision :{{usedParams.revision}} </li>
<li>resolution :{{usedParams.resolution}} </li>
<li>digital_gain :{{usedParams.digital_gain}} </li>
<li>analog_gain :{{usedParams.analog_gain}} </li>

             </ul>
         </div>
     </div> 
  </div>
</template>

<script>
import imgStats from './imgStats.vue'

export default {
  components: {
      imgStats
  },

  name: 'imgProps',
  props: {
      imgProps:Object,
      imgStats:Object,
  },
  data () {
    return {
        usedParamsSet :false,
        usedParams:false,
    }
  },
  watch:{
    imgProps:function(newval){
        if(newval.usedParams===undefined){
            this.usedParams=false    
            this.usedParamsSet = false
        }else{
            this.usedParams=newval.usedParams
            this.usedParamsSet = true
        }
    }
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
.parent {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    grid-template-rows: 1fr;
    grid-column-gap: 5px;
    grid-row-gap: 2px;

    grid-template-areas:
      "a b c d";
}

.div0 { grid-area: a; }
.div1 { grid-area: b; }
.div2 { grid-area: c; }
.div3 { grid-area: d; }
.parent > div{
    color: #ff221c;
    background: #0006;
    font-size: 14px;
      font-family: monospace, sans-serif;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
}
ul{
    padding-left: 0px;
    list-style-type:none;
}

</style>
