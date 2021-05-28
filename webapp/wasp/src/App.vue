<template>
  <div id="app">

     <div class="parent">
         <div class="div1">
             <div>
                
                 <label v-if="wsconnected">
                     connected
                 </label>
                 <label for="wsip"></label>
                 <select name="wsip" id="cars" v-model="wsip">
                        <option v-for="x in ips" :key="x" :value="x">
                                {{x}}
                        </option>
                </select> 
                <button v-on:click="onshowsettings()">Settings</button> 
                <button v-on:click="onshowstats()">Stats</button> 
                <button v-on:click="onshowmotorstats()">MotorStats</button> 
                <button v-on:click="onshowCamStats()">Caminfo</button> 
                <button v-on:click="onshowMemStats()">MemStats</button> 
             </div>
                
         </div>
         <div class="div2">
             <div v-if="wsconnected">
                 <imgDisplay v-bind:imgProps="{}" 
               v-bind:imgData="imgData"></imgDisplay >
             </div>
          </div>
          <div class="div3"> 
              <div v-show="showStats"> 
                <imgProps  v-bind:imgStats="imgStats" v-bind:imgProps="imgProps"></imgProps>
              </div>

              <div v-show="showCamStats"> 
                camera info 
                <camStats v-bind:camStats="camStats"></camStats>
              </div>
              <div v-show="showMemStats"> 
                memory info 
                <memstats v-bind:memStats="diskUsage"></memstats>
              </div>
              <div v-show="showMotorstats"> 
                <stepperControl v-bind:slidestyle="slidestyle"
                v-on:newMotorParams="newMotorParams" 
                
                ></stepperControl>
                <motorStats v-bind:motorStats="motorStats"></motorStats>

              </div>
              <div v-show="showSettings"> 
                   <captureOptions v-bind:slidestyle="slidestyle" v-on:newParams="newParams" v-on:newMotorParams="newMotorParams" ></captureOptions >
              </div>
          </div>
     </div> 
     
  </div>
</template>

<script>

import captureOptions from './components/captureOptions.vue'
import imgDisplay from './components/imgDisplay.vue'
//import imgStats from './components/imgStats.vue'
import imgProps from './components/imgProps.vue'
import motorStats from './components/motorStats.vue'
import memstats from './components/memoryStats.vue'
import camStats from './components/cameraStats.vue'
import stepperControl from './components/stepperControl.vue'

export default {
  name: 'App',
  components: {
    captureOptions,imgDisplay, imgProps,motorStats,memstats,camStats,stepperControl
  },
  data () {
    return {
        wsconnected:false,
        wsip:"192.168.1.85",
        ips:["localhost","192.168.1.22","192.168.0.40","192.168.1.85","192.168.1.37"],
        imgData:"",
        imgProps:{},
        imgStats:{},
        showSettings:true,
        showStats:true,
        showMotorstats:true,
        showCamStats:true,
        showMemStats:true,
        diskUsage:[],
        slidestyle:{
            backgroundColor: '#c7221c'
        },
        camStats:[],
        motorStats:[]
    }
  },
  methods: {
      onmessage:function(msg){
          var data = JSON.parse(msg.data)
          var msgtype = data.msgtype
          if(msgtype=="imgData"){
            this.imgData = data.data
          }
          else if(msgtype=="imgProps"){
            this.imgProps = data.data
          }
          else if(msgtype=="imgStats"){
            this.imgStats = data.data
          }
          else if(msgtype=="sysInfo"){

              //console.log("got sys info",data.data)
            this.diskUsage = data.data;//((data.data.used/data.data.total)*100).toFixed(1);
          }
          else if(msgtype=="motorInfo"){
            while(this.motorStats.length>=100){
              this.motorStats.shift();
            }

            this.motorStats.push(data);
          }else if(msgtype=="camTiming"){
            while(this.camStats.length>=100){
              this.camStats.shift();
            }

            this.camStats.push(data);
              
          }else{
            console.log(data);
          }
      },
      onopen:function(){
        this.wsconnected = true; 
      },
      onclose:function(info){
        console.log("onClose",info)
        this.wsconnected = false; 
      },
      newParams:function(params){
          if(this.wsconnected==true){
              var msg = {
                  msgtype:"params",
                data:params}
            this.connection.send(JSON.stringify(msg));
          }
      },
      newMotorParams:function(params){
          if(this.wsconnected==true){
              var msg = {
                  msgtype:"ctlparams",
                  k:params.k,
                  v:params.v}
            this.connection.send(JSON.stringify(msg));
          }
      },
      makeConnection:function(){
        this.connection = new WebSocket("ws://"+this.wsip+":8765");
        this.connection.onmessage = this.onmessage;
        this.connection.onopen = this.onopen;
        this.connection.onclose = this.onclose;

      },
      onshowmotorstats:function(){
        this.showMotorstats = !this.showMotorstats;
      },
      onshowsettings:function(){
        this.showSettings = !this.showSettings;
      },
      onshowstats:function(){
        this.showStats = !this.showStats;
      },
      onshowCamStats:function(){
        this.showCamStats = !this.showCamStats;
      },
      onshowMemStats:function(){
        this.showMemStats = !this.showMemStats;
      },

  },
  watch: {
      wsip:function(){
          console.log("resetConnection")
        this.wsconnected=false;
        this.connection.close();
        //this.makeConnection();
        setTimeout(this.makeConnection,1000);
      }
  },
  mounted: function(){
      this.makeConnection();
  },
  beforeDestroy(){
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #c7221c;
  margin-top: 0px;
  background:black;

}

.vs__selected {
    color: #c7221c;
}
.parent {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: 30px 12fr;
    grid-column-gap: 1px;
    grid-row-gap: 0px;
    
    grid-template-areas:
      "a"
      "b"
}

.div1 { grid-area: a; }
.div2 { grid-area: b; }
.div3 { grid-area: b; }

/*
.div1 { grid-area: 1 / 1 / 2 / 2; }
.div2 { grid-area: 2 / 1 / 3 / 2; }
.div3 { grid-area: 2 / 1 / 3 / 2; }
*/


button {
  color: #c7221c;
  background:black;
  border-color:#c7221c;
  font-size: 18px;
}

</style>
