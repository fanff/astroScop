
// Select the timers you're using, here ITimer1
#if ( TIMER_INTERRUPT_USING_ATMEGA_32U4 )
  #define USE_TIMER_1     true
#else
  #define USE_TIMER_1     true
  #define USE_TIMER_2     false
  #define USE_TIMER_3     false
  #define USE_TIMER_4     false
  #define USE_TIMER_5     false
#endif

#include "TimerInterrupt.h"


volatile long temp, counter = 0; //This variable will increase or decrease depending on the rotation of encoder


float P = 80;  // PID P
float I = 15 ;  // PID I
float D = 0;  // PID D

float speedGamma = .9;

float target_speed = 0;  // target speed
int HL = 3; // int version of targetspeed
const int motpinStep = 12;
const int motpinDir = 13;


volatile bool stepState = true;

void TimerHandler1(void)
{
  digitalWrite(motpinStep, stepState); 
  stepState = ! stepState;
}





void setup() {
  // put your setup code here, to run once:
  Serial.begin (9600);
  
  pinMode(2, INPUT_PULLUP); // internal pullup input pin 2 
  pinMode(3, INPUT_PULLUP); // internal pullup input pin 3
  
  //Setting up interrupt
  attachInterrupt(digitalPinToInterrupt(2), ai0, RISING);
  attachInterrupt(digitalPinToInterrupt(3), ai1, RISING);

  ITimer1.init();
  
  ITimer1.attachInterruptInterval(HL, TimerHandler1);
  

  pinMode(motpinStep, OUTPUT);
  pinMode(motpinDir, OUTPUT);


  
}




void loop() {

  delay(300); 
  checkSerial();

}


// for serial decode code
union u_tag {
   byte b[4];
   float fval;
} u;


byte paramName = 0;
byte value1 = 0;
byte value2 = 0;
byte value3 = 0;
byte value4 = 0;
byte term = 0;


void checkSerial(){
  int toread = Serial.available();
  if (toread>=6){
    paramName = Serial.read();
    value1 = Serial.read();
    value2 = Serial.read();
    value3 = Serial.read();
    value4 = Serial.read();
    term = Serial.read();

    if(term== '#'){
      u.b[0] = value1;
      u.b[1] = value2;
      u.b[2] = value3;
      u.b[3] = value4;
      
     

      if(paramName == 'P'){
        P = u.fval;
      }else if (paramName == 'I'){  
        I = u.fval;
      }else if (paramName == 'D'){  
        D = u.fval;
      }else if (paramName == 'G'){  
        speedGamma = u.fval;
      }   
      else if (paramName == 'T'){  
        target_speed = u.fval;
        HL = int(target_speed);

      }
      
    }
    else{
      // unsynced, clear all buffer
      byte stopreading = 0;
      while(Serial.available()>0 && stopreading!= 0){
        term = Serial.read();
        if(term== '#'){
          stopreading = 1;
        }
        
      }
    }

    
  }


  
}
       
void ai0() {
// ai0 is activated if DigitalPin nr 2 is going from LOW to HIGH
// Check pin 3 to determine the direction
  if(digitalRead(3)==LOW) {
  counter++;
  }else{
  counter--;
  }
}
 
void ai1() {
// ai0 is activated if DigitalPin nr 3 is going from LOW to HIGH
// Check with pin 2 to determine the direction
  if(digitalRead(2)==LOW) {
  counter--;
  }else{
  counter++;
  }
}
