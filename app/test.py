import serial
import os
from time import sleep
import serial

import paho.mqtt.client as mqtt
import json
import logging


def makePacket(speed,motorStep):
    """
    return data bytes
    """

    import struct
    
    packetFormat="bBBBBB"
    val = speed
    res=[]
    for i in [24,16,8,0]:
        div = 2**i
        v = val // div
        val = val-(v*div)
        res.append(v)
    data = struct.pack(packetFormat,*([motorStep]+res+[0]))

    return data


logging.basicConfig(level=logging.DEBUG)
log=logging.getLogger()

serialportName = os.getenv("SERIALPORT","/dev/ttyACM0")

ser = serial.Serial( serialportName, 115200) # Establish the connection on a specific port



# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    log.debug("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("arduino")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    log.debug("mqtt received "+msg.topic+" "+str(msg.payload))

    if msg.topic == "arduino":
        try:
            msgpld = msg.payload.decode("utf-8")
            data = json.loads(msgpld)
            itDelay,motorStep = data["itDelay"],data["motorStep"]
        except Exception as e:
            log.exception("bad data received with str >%s<",msgpld) 
        else:
            log.debug("sending to serial")

            
            packet = makePacket(itDelay,motorStep)
            ser.write(packet) # Convert the decimal number to ASCII then send it to the Arduino
            readLine = ser.readline() # Read the newest output from the Arduino

            log.debug(readLine)
            client.publish("arduinoReceived",readLine)

    

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)


while True:
    client.loop(timeout=1.0, max_packets=1)
    sleep(.1) # Delay in sec




