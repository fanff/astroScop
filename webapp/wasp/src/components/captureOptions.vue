<template>
  <div >
      <h3> shutterSpeed : {{ss()}}</h3>

      <button v-on:click="pushParams()">lol</button>
    {{configData()}}
    <p> 
       shootresol<v-select v-model="shootresol" :options="resols" label="name"></v-select>
       dispresol<v-select v-model="dispresol" :options="resols" label="name"></v-select>
    </p> 
    <p> 
      <VueSlideBar v-model="value1" :min=0 :max=100 :lineHeight="20"/>
      <VueSlideBar v-model="value2" :min=0 :max=1000 :lineHeight="20"/>
    </p> 
    <p> 
       iso<v-select v-model="isovalue" :options="isovalues" label="name"></v-select>
    </p> 
      
    <p> 
      <VueSlideBar v-model="redgain" :min=0 :max=300 :lineHeight="20"/>RED
      <VueSlideBar v-model="bluegain" :min=0 :max=300 :lineHeight="20"/>BLUE
    </p> 

  </div>
</template>

<script>
import VueSlideBar from 'vue-slide-bar'

import Vue from "vue"
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
      value1: 70,
      value2: 500,
      isovalue:100,
      tests: ["a","b","c"],
      isovalues: [0,100,200,300,400,500,600,700,800],
      redgain:150,
      bluegain:150,
      resols:[ {name:"tiny", width:480,height:360}, {name:"720", width:1024,height:720}, ],
      shootresol:{name:"tiny", width:480,height:360},
      dispresol: {name:"tiny", width:480,height:360},
    }
  },
  methods: {
    ss () { return 100*this.value2 + 100000*this.value1;},
    configData () { return {
        shutterSpeed:this.ss(),
        isovalue:this.isovalue,
        redgain:this.redgain,
        bluegain:this.bluegain,
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
