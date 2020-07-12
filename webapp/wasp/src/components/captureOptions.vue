<template>
  <div >
      <VueSlideBar v-model="bluegain" :min=0 :max=800 :lineHeight="20"/>BLUE

      <VueSlideBar v-model="redgain" :min=0 :max=800 :lineHeight="20"/>RED

      <VueSlideBar v-model="brightness" :min=0 :max=100 :lineHeight="20"/>Brightness
      <VueSlideBar v-model="saturation" :min=-100 :max=100 :lineHeight="20"/>Saturation
      <VueSlideBar v-model="exposure_compensation" :min=-25 :max=25 :lineHeight="20"/>Exposure

        <br/>
       iso<v-select v-model="isovalue" :options="isovalues" ></v-select>
       expomode<v-select v-model="expomode" :options="expomodes" ></v-select>
      

      <VueSlideBar v-model="value1" :min=0 :max=25 :lineHeight="20"/>
      <VueSlideBar v-model="value2" :min=0 :max=1000 :lineHeight="20"/>
        <p>
      <button v-on:click="pushParams()">lol</button>
        </p>
    <p> 
       captureMethod<v-select v-model="capture_format" :options="capture_formats" ></v-select>
       shootresol<v-select v-model="shootresol" :options="resols" label="name"></v-select>
       dispresol<v-select v-model="dispresol" :options="resols" label="name"></v-select>
       saveFormat<v-select v-model="save_format" :options="save_formats" ></v-select>
    </p> 
    <p> 
    </p> 
    <p> 
    </p> 
      

  </div>
</template>

<script>
import Vue from "vue"
import VueSlideBar from 'vue-slide-bar'

import vSelect from "vue-select"
Vue.component("v-select",vSelect)
import 'vue-select/dist/vue-select.css';

export default {
  components: {
    VueSlideBar,vSelect
  },

  name: 'captureOptions',
  props: {
  },
  data () {
    return {
      value1: 1,
      value2: 500,
      brightness:50,
      saturation:0,
      isovalue:0,
      isovalues: [0,100,200,300,400,500,600,700,800],
      capture_format : "jpeg",
      capture_formats: ["jpeg","rgb","yuv"],
      expomode : "off",
      expomodes: ["night","off","verylong","fixedfps"],
      exposure_compensation: 0,
      redgain:100,
      bluegain:100,
      resols:[ {name:"128x64", width:128,height:64},
            {name:"480x368", width:480,height:368},
          {name:"640x480", width:640,height:480},
          
           
          {name:"1280x720", width:1024,height:720}, 
          {name:"1640x1232", width:1640,height:1232}, 
      
          {name:"1920x1080", width:1920,height:1080}, 
          {name:"1920x1088", width:1920,height:1088}, 
          {name:"3280x2464", width:3280,height:2464},
          {name:"3296x2464", width:3296,height:2464},
      ],
      shootresol:{name:"480x368", width:480,height:368},
      dispresol: {name:"480x368", width:480,height:368},

      save_format:"none",
      save_formats:["none","tiff","bmp"]

    }
  },
  watch:{
    redgain:function(){this.pushParams()},
    bluegain:function(){this.pushParams()},
    isovalue:function(){this.pushParams()},
    expomode:function(){this.pushParams()},
    brightness:function(){this.pushParams()},
    value1:function(){this.pushParams()},
    value2:function(){this.pushParams()},
    exposure_compensation:function(){this.pushParams()},
    saturation:function(){this.pushParams()},
  },
  methods: {
    ss () { return 100*this.value2 + 100000*this.value1;},
    configData () { return {
        shutterSpeed:this.ss(),
        isovalue:this.isovalue,
        redgain:this.redgain/100.0,
        bluegain:this.bluegain/100.0,
        expomode:this.expomode,
        capture_format:this.capture_format,
        save_format:this.save_format,
        brightness:this.brightness,
        saturation:this.saturation,
        exposure_compensation:this.exposure_compensation,
        shootresol:this.ensureResol(this.shootresol),
        dispresol:this.ensureResol(this.dispresol),
      }
    },
    ensureResol(val){
        if(val ==false){ return this.resols[0]}
        else{return val}
    },
    pushParams(){
        var params = this.configData()

        //console.log(params);
        this.$emit("newParams",params);
    }
  },
    
  mounted(){
    //this.client = mqtt.connect("mqtt://192.168.168.3:9001");

    //this.client.on("connect",this.onConnected );

    //console.log("created mqtt client")
  },
  beforeDestroy(){
    //this.client.end()
  }
  
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
h3 {
  margin: 40px 0 0;
}
ul {
  list-style-type: none;
  padding: 0;
}
li {
  display: inline-block;
  margin: 0 10px;
}
a {
  color: #42b983;
}
.vue-slide-bar-tooltip{
    color: #c7221c;
}
</style>
