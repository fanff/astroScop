<template>
  <div >
    <img class="viewwin" alt="camimg" v-bind:src="imgsrc()" width=95% v-on:click="imgClicked">
  </div>

</template>

<script>

export default {
  components: {

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
      },
      imgClicked:function(evt){

          var pixx = (evt.pageX-evt.target.offsetLeft)/evt.target.width
          var pixy = (evt.pageY-evt.target.offsetTop)/evt.target.height

        console.log("clicked, evt",evt,pixx,pixy)
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
img {
    border-style:solid;
    border-color:#a7021c;
}
</style>
