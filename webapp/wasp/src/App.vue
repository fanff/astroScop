<template>
  <div id="app">

     <div class="parent">
         <div class="div1">
             <div>
                
                 <label for="wsip"></label>
                 <select name="wsip" id="cars" v-model="wsip">
                        <option v-for="x in ips" :key="x" :value="x">
                                {{x}}
                        </option>
                </select> 
                <button v-on:click="onshowsettings()">Settings</button> 
                <button v-on:click="onshowstats()">Stats</button> 
                {{diskUsage}}
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
                <imgStats v-bind:imgStats="imgStats"></imgStats>
                <imgProps v-bind:imgProps="imgProps"></imgProps>
              </div>
              <div v-show="showSettings"> 
                   <captureOptions v-on:newParams="newParams" ></captureOptions >
              </div>
          </div>
     </div> 
     
  </div>
</template>

<script>

import captureOptions from './components/captureOptions.vue'
import imgDisplay from './components/imgDisplay.vue'
import imgStats from './components/imgStats.vue'
import imgProps from './components/imgProps.vue'

export default {
  name: 'App',
  components: {
    captureOptions,imgDisplay,imgStats, imgProps
  },
  data () {
    return {
        wsconnected:false,
        wsip:"192.168.1.22",
        ips:["localhost","192.168.1.22"],
        imgData:"",
        imgProps:{},
        imgStats:{},
        showSettings:true,
        showStats:true,
        diskUsage:"?",
    }
  },
  methods: {
      onmessage:function(msg){
          var data = JSON.parse(msg.data)
          var msgtype = data.type
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
            this.diskUsage = ((data.data.used/data.data.total)*100).toFixed(1);
          }else{
            console.log(data);
          }
      },
      onopen:function(){
        this.wsconnected = true; 
      },
      onclose:function(){
        console.log("onClose")
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
      makeConnection:function(){
        this.connection = new WebSocket("ws://"+this.wsip+":8765");
        this.connection.onmessage = this.onmessage;
        this.connection.onopen = this.onopen;
        this.connection.onclose = this.onclose;

      },
      onshowsettings:function(){
        this.showSettings = !this.showSettings;
      },
      onshowstats:function(){
        this.showStats = !this.showStats;
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
    grid-template-rows: 1fr 12fr;
    grid-column-gap: 1px;
    grid-row-gap: 0px;
}

.div1 { grid-area: 1 / 1 / 2 / 2; }
.div2 { grid-area: 2 / 1 / 3 / 2; }
.div3 { grid-area: 2 / 1 / 3 / 2; }


</style>
