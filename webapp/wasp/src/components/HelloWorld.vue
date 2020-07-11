<template>
  <div class="hello">
    <h1>{{durationValue() }} {{ msg }}</h1>
    <p>
    {{mqttConnected}}
    </p>
    <p>
      For a guide and recipes on how to configure / customize this project,<br>
        
      <VueSlideBar v-model="value1"
    :min=0
        :max=1000000
    :lineHeight="20"
      />
      <VueSlideBar v-model="value2"
    :min=0
        :max=200000
    :lineHeight="20"
      />
      <VueSlideBar v-model="value3"
    :min=0
        :max=50000
    :lineHeight="20"
      />
      <VueSlideBar v-model="value4"
    :min=0
        :max=10000
    :lineHeight="20"
      />
      <VueSlideBar v-model="value5"
    :min=0
        :max=3000
    :lineHeight="20"
      />
      <VueSlideBar v-model="value6"
    :min=0
        :max=700
    :lineHeight="20"
      />
      <VueSlideBar v-model="value7"
    :min=0
        :max=100
    :lineHeight="20"
      />
    </p>
    <h3>Installed CLI Plugins</h3>
    <ul>
      <li><a href="https://github.com/vuejs/vue-cli/tree/dev/packages/%40vue/cli-plugin-babel" target="_blank" rel="noopener">babel</a></li>
      <li><a href="https://github.com/vuejs/vue-cli/tree/dev/packages/%40vue/cli-plugin-eslint" target="_blank" rel="noopener">eslint</a></li>
    </ul>
    <h3>Essential Links</h3>
    <ul>
      <li><a href="https://vuejs.org" target="_blank" rel="noopener">Core Docs</a></li>
      <li><a href="https://forum.vuejs.org" target="_blank" rel="noopener">Forum</a></li>
      <li><a href="https://chat.vuejs.org" target="_blank" rel="noopener">Community Chat</a></li>
      <li><a href="https://twitter.com/vuejs" target="_blank" rel="noopener">Twitter</a></li>
      <li><a href="https://news.vuejs.org" target="_blank" rel="noopener">News</a></li>
    </ul>
    <h3>Ecosystem</h3>
    <ul>
      <li><a href="https://router.vuejs.org" target="_blank" rel="noopener">vue-router</a></li>
      <li><a href="https://vuex.vuejs.org" target="_blank" rel="noopener">vuex</a></li>
      <li><a href="https://github.com/vuejs/vue-devtools#vue-devtools" target="_blank" rel="noopener">vue-devtools</a></li>
      <li><a href="https://vue-loader.vuejs.org" target="_blank" rel="noopener">vue-loader</a></li>
      <li><a href="https://github.com/vuejs/awesome-vue" target="_blank" rel="noopener">awesome-vue</a></li>
    </ul>
  </div>
</template>

<script>
import VueSlideBar from 'vue-slide-bar'

import mqtt from 'mqtt'

export default {
  components: {
    VueSlideBar
  },

  name: 'HelloWorld',
  props: {
    msg: String
  },
  data () {
    return {
      value1: 500000,
      value2: 0,
      value3: 0,
      value4: 0,
      value5: 0,
      value6: 0,
      value7: 0,
      mqttConnected: false,
    }
  },
  methods: {
    durationValue () {
      return this.value1+this.value2+this.value3+this.value4+this.value5+this.value6+this.value7
    },
    onConnected(){
        this.mqttConnected = true;
        console.log("connected")
    }
  },
  mounted(){
    this.client = mqtt.connect("mqtt://192.168.168.3:9001");

    this.client.on("connect",this.onConnected );

    console.log("created mqtt client")
  },
  beforeDestroy(){
    this.client.end()
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
</style>
