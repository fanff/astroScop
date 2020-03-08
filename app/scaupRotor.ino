
/*
 Stepper Motor Control - one step at a time

 This program drives a unipolar or bipolar stepper motor.
 The motor is attached to digital pins 8 - 11 of the Arduino.

 The motor will step one step at a time, very slowly.  You can use this to
 test that you've got the four wires of your stepper wired to the correct
 pins. If wired correctly, all steps should be in the same direction.

 Use this also to count the number of steps per revolution of your motor,
 if you don't know it.  Then plug that number into the oneRevolution
 example to see if you got it right.

 Created 30 Nov. 2009
 by Tom Igoe

 */
#include <TimerOne.h>
#include <Stepper.h>

const int stepsPerRevolution = 200;  // change this to fit the number of steps per revolution
// for your motor

// initialize the stepper library
Stepper myStepper(stepsPerRevolution, 6, 7, 8, 9);

int stepCount = 0;         // number of steps the motor has taken


boolean newData = false;
const byte numChars = 3;
uint8_t receivedChars[numChars]; // an array to store the received data

void setup() {
  // initialize the serial port:
  Timer1.initialize(2000000);
  Timer1.attachInterrupt(stepMotor);


  
}
void recvWithEndMarker() {
 static byte ndx = 0;
 char endMarker = 0;
 char rc;
 
 // 
 while (Serial.available() > 0 && newData == false) {
   rc = Serial.read();
  
   if (rc != endMarker) {
     receivedChars[ndx] = rc;
     ndx++;
     if (ndx >= numChars) {
      ndx = numChars - 1;
     }
   } else {
     receivedChars[ndx] = '\0'; // terminate the string
     ndx = 0;
     newData = true;
   }
 }
}


void stepMotor(){
  myStepper.step(1);
}

void setMotorSpeed() {
 if (newData == true) {
    receivedChars[0];
    receivedChars[1];
    newData=false;
 }
}

void loop() {
  unsigned long p = 20L*1000L  ;
  Timer1.setPeriod(p);
  recvWithEndMarker();

  setMotorSpeed();
  
  
}
