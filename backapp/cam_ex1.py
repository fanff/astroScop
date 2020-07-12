from time import sleep
from picamera import PiCamera
import time
import imgutils
#pports 1080p @ 30fps, 720p @ 60fps and 640x480p 60/90 Recording
import logging
from io import BytesIO
from PIL import Image
import json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

['night', "off" ,"verylong","fixedfps"]
#camera.exposure_mode

freshParams = None

def cleanParams(params):
    if params == None :
        return {
        "shutterSpeed": 150000,
        "isovalue": 100,
        "redgain": 1.0 ,
        "bluegain": 1.0,
        }
    else:
        params["shutterSpeed"]
        params["isovalue"]
        params["redgain"]
        params["bluegain"]
        params["expomode"]

        return params

from websocket import create_connection
ws = create_connection("ws://localhost:8765/camera")

log.info("openingcamera")
with PiCamera(resolution=(1024, 768), framerate_range=(0.1,30)) as camera:
    log.info("got camera")
    # Set ISO to the desired value
    continueLoop=True
    while continueLoop:

        params = cleanParams(freshParams)

        camera.iso = params["isovalue"]
        log.info("analog_gain %s",camera.analog_gain)
        
        #camera.analog_gain=1.0 
        camera.exposure_mode = "fixedfps"
        
        camera.shutter_speed =params["shutterSpeed"]
        log.info("exposure speed %s" , camera.exposure_speed)
        
        g=(params["redgain"],params["bluegain"])

        camera.awb_mode = 'off'
        camera.awb_gains = g
        # Finally, take several photos with the fixed settings
    
        log.info("capture start %s"%params)
        triggerDate = time.time()
        stream = BytesIO()

        camera.capture(stream,format="jpeg")

        stream.seek(0)
        image = Image.open(stream)

        end = time.time()
        dur = end-triggerDate
        log.info("capture ended in  %.2fsec",dur)
        
        strtTime = time.time()
        try:
            data = imgutils.pilimTobase64Jpg(image)
            ws.send(json.dumps({
                "usedParams":{
                    "triggerDate": triggerDate,
                    "gains" :g,
                    "analog_gain":float(camera.analog_gain), 
                    "iso" :camera.iso,
                    "shutterSpeeed":camera.shutter_speed,
                    "exposure_speed":camera.exposure_speed,
                    "exposure_mode":camera.exposure_mode,
                    "capture_dur":dur,
                    },
                "msgtype":"srcimage",
                "imageData":data}))

            freshParams =  json.loads(ws.recv())


        except Exception as e:
            log.exception("err %s",e)


        dur = time.time()-strtTime
        log.info("sending ended in  %.2fsec",dur)

ws.close()


