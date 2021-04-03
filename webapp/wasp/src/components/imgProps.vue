<template>
  <div >
     <div v-show="usedParamsSet" class="parent">
         <div class="div1"> 
             <ul>
                 <li>{{usedParams.triggerDateStr}}</li>
                 <li>isovalue: {{usedParams.isovalue}}</li>
                 <li>red gain:{{usedParams.redgain}}</li>
                 <li>blue gain:{{usedParams.bluegain}}</li>
                 <li>bright:{{usedParams.brightness}}</li>
                 <li>sat:{{usedParams.saturation}}</li>
                 <li>exposure:{{usedParams.exposure_compensation}}</li>
                 <li>contrast:{{usedParams.contrast}}</li>
                 <li>iso: {{usedParams.isovalue}}</li>
                 <li>shutter: {{usedParams.shutterSpeed}}</li>
             </ul>
         </div>
         <div class="div2"> 
             <ul>
                 <li>shoot at: {{usedParams.shootresol.name}}</li>
                 <li>display at:{{usedParams.dispresol.name}}</li>
                 <li>awb_mode:{{usedParams.awb_mode}}</li>
                 <li>exposure_mode:{{usedParams.expomode}}</li>
                 <li>capture_format: {{usedParams.capture_format}}</li>
                 <li>save_format: {{usedParams.save_format}}</li>
                 <li>fdest: {{usedParams.fdest}}</li>
                 <li>filename: {{usedParams.fileNameExt}}</li>
             </ul>
         </div>
     </div> 
  </div>
</template>

<script>

export default {
  components: {
  },

  name: 'imgProps',
  props: {
      imgProps:Object,
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
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: 1fr;
    grid-column-gap: 2px;
    grid-row-gap: 2px;
}

.div1 { grid-area: 1 / 1 / 2 / 2; }
.div2 { grid-area: 1 / 2 / 2 / 3; }

ul{
    list-style-type:none;
}

</style>
