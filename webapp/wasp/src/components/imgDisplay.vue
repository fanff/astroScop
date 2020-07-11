<template>
  <div class="hello">
    <img alt="camimg" v-bind:src="imgsrc()" width=500>
  
    <trend :data="bvals" :gradient="['#00F']" auto-draw></trend>
    <trend :data="gvals" :gradient="['#0F0']" auto-draw></trend>
    <trend :data="rvals" :gradient="['#F00']" auto-draw></trend>
  <p>
  props : {{imgProps}}
  </p>
  </div>

</template>

<script>
import Trend from "vuetrend"
export default {
  components: {
    Trend
  },

  name: 'imgDisplay',
  props: {
    imgData: String,
    imgStats: Object,
    imgProps: Object
  },
  data () {
    return {
        bvals:[],
        gvals:[],
        rvals:[],
    }
  },
  methods: {

      imgsrc:function(){
        return 'data:image/jpeg;base64, '+this.imgData;
      }
  },
  watch:{
    imgStats:function(newval){
        //console.log("imgstats ",newval)
        this.bvals=newval["histData"][0]
        this.gvals=newval["histData"][1]
        this.rvals=newval["histData"][2]
            
        //this.vals.shift()
    }
  },
  mounted(){
  },
  beforeDestroy(){
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
