import Vue from 'vue'
import App from './App.vue'

Vue.config.productionTip = false
//import mqtt from 'mqtt'

new Vue({
  render: h => h(App),
}).$mount('#app')
