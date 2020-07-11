from time import sleep
from picamera import PiCamera
import time
import imgutils
#pports 1080p @ 30fps, 720p @ 60fps and 640x480p 60/90 Recording
import logging
from io import BytesIO
from PIL import Image

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

['night', "off" ,"verylong","fixedfps"]


from websocket import create_connection


from websocket import create_connection


quit()
log.info("openingcamera")
with PiCamera(resolution=(640, 480), framerate_range=(0.166666,30)) as camera:
    log.info("got camera")
    # Set ISO to the desired value
    camera.iso = 100
    log.info("analog_gain %s",camera.analog_gain)
    
    #camera.analog_gain=1.0 
    camera.exposure_mode = "fixedfps"
    
    camera.shutter_speed =3000000
    log.info("exposure speed %s" , camera.exposure_speed)
    
    g=(1.0,1.0)
    log.info("setting  awg_gains %s",g)

    camera.awb_mode = 'off'
    camera.awb_gains = g
    # Finally, take several photos with the fixed settings
    
    for i in range(6):
        log.info("capture start ")
        strt = time.time()
        stream = BytesIO()

        camera.capture(stream,format="jpeg")

        stream.seek(0)
        image = Image.open(stream)

        end = time.time()
        log.info("capture end ")
        
        ws = create_connection("ws://localhost:8765/")
        ws.send({"imageData":"l"})

        dur = end-strt
        log.info("capture dur %.2fsec",dur)


