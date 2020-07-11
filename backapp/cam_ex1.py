from time import sleep
from picamera import PiCamera

import imgutils
#pports 1080p @ 30fps, 720p @ 60fps and 640x480p 60/90 Recording

camera = PiCamera(resolution=(720, 720), framerate=1/6,sensor_mode=3)
# Set ISO to the desired value
camera.iso = 100
# Wait for the automatic gain control to settle

print("sleeping")
sleep(2)
# Now fix the values

print("exposure speed" , camera.exposure_speed)
camera.shutter_speed = 6000000
camera.exposure_mode = 'off'
g= [float(_) for _ in camera.awb_gains]

print(g)

camera.awb_mode = 'off'
camera.awb_gains = g
# Finally, take several photos with the fixed settings

print("capture start ")
strt = time.time()
camera.capture_sequence(['image%02d.jpg' % i for i in range(1)])
end = time.time()
print("capture end ")

dur = end-strt
print("capture dur ")


