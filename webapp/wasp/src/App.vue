<template>
  <div id="app">

      <div v-if="wsconnected">
        <imgDisplay v-bind:imgProps="imgProps" 
        v-bind:imgStats="imgStats"
        v-bind:imgData="imgData"></imgDisplay >
        <captureOptions v-on:newParams="newParams" ></captureOptions >
      </div>
      <div v-else>
      
      </div>
       <v-select v-model="wsip" :options="ips" ></v-select>
  </div>
</template>

<script>

import captureOptions from './components/captureOptions.vue'
import imgDisplay from './components/imgDisplay.vue'

export default {
  name: 'App',
  components: {
    captureOptions,imgDisplay
  },
  data () {
    return {
        wsconnected:false,
        wsip:"localhost",
        ips:["localhost","192.168.1.22"],
        imgData:"",
        imgProps:{},
        imgStats:{},
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

      }
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


</style>
