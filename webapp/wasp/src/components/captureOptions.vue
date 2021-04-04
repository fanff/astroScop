<template> <div>
<div class="parent">
    <div class="cg">
      <VueSlideBar v-model="bluegain" :min=0 :max=800 
        :processStyle="{backgroundColor: slidestyle.backgroundColor, color:'blue' }"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>
      BLUE

      <VueSlideBar v-model="redgain" :min=0 :max=800 
                   :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>RED
      
        
        <VueSlideBar v-model="analog_gain" :min=100 :max=800
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>

       analog_gain
      <VueSlideBar v-model="digital_gain" :min=100 :max=800
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>
       digital_gain
    </div >


    <div class="bcss">
      <VueSlideBar v-model="brightness" :min=0 :max=100
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor,color: 'black'  }"/>Brightness

      <VueSlideBar v-model="contrast" :min=-100 :max=100 
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>Contrast
      <VueSlideBar v-model="saturation" :min=-100 :max=100 
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>Saturation
      <VueSlideBar v-model="sharpness" :min=-100 :max=100 
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>Sharpness
      <VueSlideBar v-model="exposure_compensation" :min=-25 :max=25  
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>Exposure

    </div >


    <div class="ie">
       iso<v-select v-model="isovalue" :options="isovalues" ></v-select>
       expomode<v-select v-model="expomode" :options="expomodes" ></v-select>
        
      captureMethod<v-select v-model="capture_format" :options="capture_formats" ></v-select>
      shootresol<v-select v-model="shootresol" :options="resols" label="name"></v-select>

      denoise<v-select v-model="denoise" :options="denoise_opts" label="name"></v-select>
    </div >


    <div class="ss">
      <VueSlideBar v-model="value1" :min=0 :max=120
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor ,color: 'black' }"/>
      <VueSlideBar v-model="value2" :min=0 :max=10000 
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor,color: 'black'  }"/>
       
    </div >


    <div class="saveopt">
      dispresol<v-select v-model="dispresol" :options="resols" label="name"></v-select>
      saveFormat<v-select v-model="save_format" :options="save_formats" ></v-select>
      saveSection<v-select v-model="save_section" :options="save_sections" ></v-select>

      subsection  <input v-model="save_subsection" >
      
      <button v-on:click="pushParams()">pushparams</button>
    </div >




    <div class="motoropt">
      <VueSlideBar v-model="motorSpdSlider" :min=-10000 :max=10000 
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor,color: 'black'  }"/>
      speed {{ calcSpeed() }}

        <p>
      <button v-on:click="incSpeed(-100)">-100</button>
      <button v-on:click="incSpeed(-10)">-10</button>
      <button v-on:click="incSpeed(-1)">-1</button>
      <button v-on:click="setSpeed(0)">0</button>
      <button v-on:click="incSpeed(1)">+1</button>
      <button v-on:click="incSpeed(10)">+10</button>
      <button v-on:click="incSpeed(100)">+100</button>
        </p>
      <button v-on:click="pushMotorParams()">push Ctl Params</button>

    </div >


</div >
  
</div></template>

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
      slidestyle:{
          backgroundColor: 'blue'
      }
  },
  data () {
    return {
      value1: 1,
      value2: 500,
      brightness:50,
      saturation:0,
      contrast:0,
      sharpness:0,
      isovalue:0,
      isovalues: [0,100,200,300,400,500,600,700,800],
      capture_format : "rgb",
      capture_formats: ["jpeg","rgb","yuv"],
      expomode : "off",
      expomodes: ["night","off","verylong","fixedfps"],
      exposure_compensation: 0,
      redgain:100,
      bluegain:100,
      digital_gain:100,
      analog_gain:100,
      resols:[ {name:"128x64", width:128,height:64, mode:0},
          {name:"640x480", width:640,height:480, mode:0},
          {name:"1280x720", width:1024,height:720, mode:0}, 
          {name:"1332x990 HQ 2bin", width:1332,height:990, mode:0}, 
          {name:"1640x1232", width:1640,height:1232, mode:0}, 
          {name:"1920x1080", width:1920,height:1080, mode:0}, 
          {name:"2028x1520 HQ 2bin", width:2028,height:1520, mode:0},
          {name:"4056x3040 HQ Nat", width:4056,height:3040, mode:0},
          
          
          {name:"2028x1088 3B (1)", width:2028,height:1088, mode:1},
          {name:"1012x760 3B (4)", width:1012,height:760, mode:4},
      ],
      shootresol:{name:"128x64", width:128,height:64,mode:0},
      dispresol: {name:"128x64", width:128,height:64,mode:0},
        
    denoise_opts:[{name:true},{name:false}],
    denoise: [{name:true}],
      save_format:"none",
      save_formats:["none","tiff","bmp"],
      
      save_section:"work",
      save_sections:["work","test","deep","planet","dark","flats"],
      
      save_subsection:"",
        

      motorSpdSlider:0.0,

    }
  },
  watch:{
    redgain:function(){this.pushParams()},
    bluegain:function(){this.pushParams()},
    brightness:function(){this.pushParams()},
    saturation:function(){this.pushParams()},
    sharpness:function(){this.pushParams()},
    contrast:function(){this.pushParams()},
    exposure_compensation:function(){this.pushParams()},

    isovalue:function(){this.pushParams()},
    expomode:function(){this.pushParams()},
    analog_gain:function(){this.pushParams()},
    digital_gain:function(){this.pushParams()},
    value1:function(){this.pushParams()},
    value2:function(){this.pushParams()},

    capture_format:function(){this.pushParams()},
    shootresol:function(){this.pushParams()},
    denoise:function(){this.pushParams()},
    dispresol:function(){this.pushParams()},
    save_format:function(){this.pushParams()},
    save_section:function(){this.pushParams()},
    save_subsection:function(){this.pushParams()},
  },
  methods: {
    calcSpeed(){
        return ( this.motorSpdSlider / 10000)*4.0
    },
    ss () { return 10*this.value2 + 100000*this.value1;},
    configData () { return {
        shutterSpeed:this.ss(),
        isovalue:this.isovalue,
        redgain:this.redgain/100.0,
        bluegain:this.bluegain/100.0,
        analog_gain:this.analog_gain/100.0,
        digital_gain:this.digital_gain/100.0,
        expomode:this.expomode,
        capture_format:this.capture_format,
        brightness:this.brightness,
        saturation:this.saturation,
        sharpness:this.sharpness,
        contrast:this.contrast,
        exposure_compensation:this.exposure_compensation,
        shootresol:this.ensureResol(this.shootresol),
        dispresol:this.ensureResol(this.dispresol),
        denoise:this.denoise.name,
        save_format:this.save_format,
        save_section:this.save_section,
        save_subsection:this.save_subsection,
      }
    },
    setSpeed(val){
        this.motorSpdSlider = val;
    },
    incSpeed(val){
        this.motorSpdSlider = this.motorSpdSlider+ val;
    },
    ensureResol(val){
        if(val ==false){ return this.resols[0]}
        else{return val}
    },
    pushParams(){
        var params = this.configData()

        //console.log(params);
        this.$emit("newParams",params);
    },
    pushMotorParams(){
        var params = {k:"T",v:this.calcSpeed()}

        //console.log(params);
        this.$emit("newMotorParams",params);
    }
  },
    
  mounted(){
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

input {
  color: #c7221c;
  background-color: black;
  border-color:#c7221c;
}

.parent {
    display: grid;
    grid-template-columns: 1fr  2fr  2fr;
    grid-template-rows: 1fr 1fr;
    grid-column-gap: 2px;
    grid-row-gap: 2px;

    grid-template-areas:
      "a b c"
      "e s f";
}

.cg { grid-area: c; }
.bcss { grid-area: b; }
.ie { grid-area: a; }
.ss { grid-area: s; }
.saveopt { grid-area: e; }
.motoropt { grid-area: f; }
.parent > div{

    background: #0007;
}
</style>
