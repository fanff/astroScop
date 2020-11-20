volatile long temp, counter = 0; //This variable will increase or decrease depending on the rotation of encoder

float rspd = 0 ; // read speed

float target_speed = 0;  // target speed

float err = 0; // PID Error
float errprev = 0; // PID Error
float errcum = 0; // PID Error cumulated

float P = -10;  // PID P
float I = 0;  // PID I
float D = 0;  // PID D

int cmd = 0;  // command to motor

const int motpin1 = 9;
const int motpin2 = 10;

float rspdArr[10] = {0,0,0,0,0};
int rspdidx = 0;
float meanSpeed = 0;


#define DEBUGSERIAL

void setup() {

  #ifdef DEBUGSERIAL
    Serial.begin (9600);
  #endif
  

  
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

  
    rspd = float(temp);
    rspdArr[rspdidx] = rspd;
    rspdidx+=1;
    if (rspdidx>=10){rspdidx=0;}


    // calculate mean speed.
    meanSpeed=0;
    for(int i=0;i<10;i++){
      
      meanSpeed+=rspdArr[i];
    }
    meanSpeed = meanSpeed/10;
  
  
  // sensorValue -> target speed
  err = target_speed - rspd;
  

  cmd = err*P +(err-errprev)*D + errcum*I;

  // keep error 
  errprev = err;

  // sum error
  errcum +=err;
  if(errcum > 50){errcum=50;}
  if(errcum < -50){errcum=-50;}

  
  if (cmd>0){
    goBackward(cmd);
  }else{
    goForward(-cmd);
  }
  #ifdef DEBUGSERIAL
    Serial.print("rspd:" );
    Serial.print(rspd);
  
    Serial.print(" mspd:" );
    Serial.print(meanSpeed);
    
    Serial.print(" ts:" );
    Serial.print(target_speed);
  
    Serial.print(" p:" );
    Serial.print(P/10);
  
    Serial.print(" I:" );
    Serial.print(I/10);
    
     
    Serial.print(" err:" );
    Serial.print(err);
    
    Serial.print(" cmd:" );
    Serial.print(float(cmd)/255);
   
   
    Serial.println("" );
  #endif

  delay(500);
  
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
