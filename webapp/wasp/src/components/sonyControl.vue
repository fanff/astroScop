<template>
  <div >
        sony Control
        {{seqinfo}}
        <button v-on:click="$emit('sonyShoot',countPict);">shoot!</button>
        <input v-model="countPict" />
        
        <table>
                <caption>Sony Control</caption>
                <tr>
                          <th>Label</th>
                              <th>Key</th>
                              <th>NewVal</th>
                              <th>Current</th>
                              <th></th>
                </tr>
            <tr v-for="item in filterChoicableFields()" :key="item.key">


                <td> 
                    {{ item.label }}
                
                </td>
                <td> 
                
                    ({{ item.key }})
                </td>
                <td> 
                <select v-model="currentBuff[item.key] " label="item.label">
                    

                        <option v-for="choice in item.choices" 
                            :key="choice[0]"
                            :value="choice[0]"
                            >
                            ({{choice[0]}}) {{choice[1]}}
                        </option>
                </select>
                </td>
                <td> 
                    {{currentCameraConfigForKey(item.key) }}
                </td>
                <td> 
                    <button v-on:click="pushConfig()">push</button>
                </td>
            </tr>
        </table>
        


  </div>
</template>

<script>
//import Vue from "vue"

import defaultSonyConfig from '../assets/defaultSonyConfig.json'

export default {
  components: {
  },
  name: 'sonyControl',
  props: {
      cameraConfig:Array,
      seqinfo :Object,
  },
  data () {
    return {

        statusString:"noStatus",
        defaultSonyConfig:defaultSonyConfig,
        latestSonyConfig:defaultSonyConfig,
        currentBuff:{},

        countPict:1,

    }
  },
  watch:{
      cameraConfig:function(newval){
        this.latestSonyConfig=newval
      }
  },
  methods: {
      currentCameraConfigForKey(key){
          var vals = this.cameraConfig.filter(function(val){return val.key==key})
          if(vals.length>0){
            return vals[0].Current
          }
          else{return "noInfo"}
      },
      filterChoicableFields(){
          return this.defaultSonyConfig.filter(function(val){ return val.choices.length>0 && val.ro=="0"});
      },
      pushConfig(){
        this.$emit("sonyConfig_param",this.currentBuff);
        this.currentBuff = {}
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
