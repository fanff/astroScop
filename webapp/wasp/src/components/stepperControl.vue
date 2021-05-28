
<template>
  <div >
    <div class="motoropt">
        <input type="checkbox" id="checkbox" v-model="checked">
        <label for="checkbox">DirectControl</label>
        <br/>
      
      <span>ASC</span>
        <select v-model="motorAscCurr">
                             <option>300</option>
                             <option>1000</option>
                             <option>1500</option>
                             <option>2000</option>
        </select>
        <select v-model="spdRangeAsc">
            <option v-for="key,option in this.spdRangesDict" v-bind:key="option">
                {{ option }}
                  </option>
        </select>
        
        <button v-on:click="resetDriver('ASC_RESET')">resetDriver</button>
        <button v-on:click="motorAscSpd=0">stop</button>


      <VueSlideBar v-model="motorAscSpd" :min="spdRangesDict[spdRangeAsc].min" :max="spdRangesDict[spdRangeAsc].max"
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor,color: 'black'  }"/>
        
      
        <span>DEC</span>
        <select v-model="motorDecCurr">
                             <option>300</option>
                             <option>1000</option>
                             <option>1500</option>
                             <option>2000</option>
        </select>
        <select v-model="spdRangeDec">
            <option v-for="key,option in this.spdRangesDict" v-bind:key="option">
                {{ option }}
                  </option>
        </select>
        <button v-on:click="resetDriver('DEC_RESET')">resetDriver</button>
        <button v-on:click="motorDecSpd=0">stop</button>
        
      <VueSlideBar v-model="motorDecSpd" :min="spdRangesDict[spdRangeDec].min" :max="spdRangesDict[spdRangeDec].max" 
        :processStyle="{backgroundColor: slidestyle.backgroundColor}"
        :lineHeight="10"
        :tooltipStyles="{ backgroundColor: slidestyle.backgroundColor, borderColor: slidestyle.backgroundColor,color: 'black'  }"/>

    </div >
        <button v-on:click="zeroLocation('ASC_ZERO')">ZeroASC</button>
        <button v-on:click="zeroLocation('DEC_ZERO')">ZeroDEC</button>

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
      VueSlideBar
  },

  name: 'stepperControl',
  props: {
      slidestyle:{
          backgroundColor: 'blue'
      }
  },
  data () {
    return {
        checked:false,
        spdRangeDec:"fast",
        motorDecCurr:300,
        motorDecSpd:0,

        spdRangeAsc:"fast",
        motorAscCurr:300,
        motorAscSpd:0,
        
        
        spdRangesDict:{
            slow:{min:-2000,max:2000},
            medium:{min:-7000,max:7000},
            fast:{min:-150000,max:150000},
            right_slow:{min:0,max:2000},
        }

    }
  },
  watch:{

      spdRangeAsc:function(newRangeKey){

          var min = this.spdRangesDict[newRangeKey].min 
          var max = this.spdRangesDict[newRangeKey].max 
          if(this.motorAscSpd<min){
            this.motorAscSpd = min
          }
          if(this.motorAscSpd>max){
            this.motorAscSpd = max
          }
      },
      spdRangeDec:function(newRangeKey){

          var min = this.spdRangesDict[newRangeKey].min 
          var max = this.spdRangesDict[newRangeKey].max 
          if(this.motorDecSpd<min){
            this.motorDecSpd = min
          }
          if(this.motorDecSpd>max){
            this.motorDecSpd = max
          }
      },
      motorDecCurr:function(newCurr){
          if(this.checked){
            this.pushMotorParams({k:"DEC_CURR",v:newCurr});
          }
      },
      motorAscCurr:function(newCurr){
          if(this.checked){
              this.pushMotorParams({k:"ASC_CURR",v:newCurr});
          }
      },
      motorDecSpd:function(newSpeed){
          //console.log("speed changed",newSpeed)
          if(this.checked){
            this.pushMotorParams({k:"DEC",v:newSpeed});
          }
      },
      motorAscSpd:function(newSpeed){
          //console.log("speed changed",newSpeed)
          if(this.checked){
              this.pushMotorParams({k:"ASC",v:newSpeed});
          }
      }
  },
  methods: {
    zeroLocation(key){

        if(this.checked){
            this.pushMotorParams({k:key,v:0});
        }
    },
    speedMethodsKeys(){

        return this.spdRangesDict.keys()   
    },
    resetDriver(key){

        //console.log(params);
        this.$emit("newMotorParams",{"k":key,v:0});
    },
    pushMotorParams(params){

        //console.log(params);
        this.$emit("newMotorParams",params);
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
