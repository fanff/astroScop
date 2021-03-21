volatile long temp, counter = 0; //This variable will increase or decrease depending on the rotation of encoder

float rspd = 0 ; // read speed

float target_speed = 0;  // target speed

float err = 0; // PID Error
float errprev = 0; // PID Error
float errcum = 0; // PID Error cumulated

float P = 80;  // PID P
float I = 15 ;  // PID I
float D = 0;  // PID D

int cmd = 0;  // command to motor

const int motpin1 = 9;
const int motpin2 = 10;

float speedGamma = .9;

float meanSpeed = 0;


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




void setup() {
  Serial.begin (9600);
  
  pinMode(2, INPUT_PULLUP); // internal pullup input pin 2 
  pinMode(3, INPUT_PULLUP); // internal pullup input pin 3
  
  //Setting up interrupt
  attachInterrupt(digitalPinToInterrupt(2), ai0, RISING);
  attachInterrupt(digitalPinToInterrupt(3), ai1, RISING);


  pinMode(motpin1, OUTPUT);
  pinMode(motpin2, OUTPUT);
}


   
void loop() {
  // Send the value of counter
  noInterrupts();
  temp = counter;
  counter=0;
  // critical, time-sensitive code here
  interrupts();

  // cast read speed to float
  rspd = float(temp);

  // calculate mean speed.
  meanSpeed= meanSpeed*speedGamma + rspd * (1.0-speedGamma) ;
    
  
  
  // sensorValue -> target speed
  err = target_speed - meanSpeed;
  
  // sum error
  errcum +=err;
  if(errcum > 15){errcum=15;}
  if(errcum < -15){errcum=-15;}

  // calculate command
  cmd = (err*P) +  ( (err-errprev)*D )  + ( errcum*I) ;

  // keep error 
  errprev = err;

  //
  if (cmd>0){
    goBackward(cmd);
  }else{
    goForward(-cmd);
  }

  
  printValues();
  
  checkSerial();
  delay(200);

  
}


void printValues(){

    Serial.print("rspd:" );
    Serial.print(rspd);
  
    Serial.print(" mspd:" );
    Serial.print(meanSpeed,6);
    
    Serial.print(" ts:" );
    Serial.print(target_speed,6);
     
    Serial.print(" err:" );
    Serial.print(err,6);

    
      /*
    Serial.print(" pn:" );
    Serial.print(paramName);

    Serial.print(" term:" );
    Serial.print(term);


    Serial.print(" fval:" );
    Serial.print(u.fval,6);


    Serial.print(" v1:" );
    Serial.print(value1);
    Serial.print(" v2:" );
    Serial.print(value2);
    Serial.print(" v3:" );
    Serial.print(value3);
    Serial.print(" v4:" );
    Serial.print(value4);
  
    */
    Serial.print(" cmd:" );
    Serial.print(float(cmd)/100);
   
    Serial.println("" );
  
  
}


  
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

const int DUTYLOWLIMIT = 20;
void goForward(int duty){

  if (duty<DUTYLOWLIMIT){motStop();}
  else if (duty>255){goForward(255);}
  else{
    analogWrite(motpin1, duty);
    digitalWrite(motpin2, LOW);
  
  }
  
}

void goBackward(int duty){
  if (duty<DUTYLOWLIMIT){motStop();}
  else if (duty>255){goBackward(255);}
  else{
    digitalWrite(motpin1, LOW);
    analogWrite(motpin2, duty); 
  } 
}

void motStop(){
  digitalWrite(motpin1, LOW);
  digitalWrite(motpin2, LOW);

}
