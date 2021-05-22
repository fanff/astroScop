/**

 */

#include <TMCStepper.h>

#define EN_PIN           5 // Enable
#define DIR_PIN          7 // Direction
#define STEP_PIN         6 // Step
#define SW_RX            9 // TMC2208/TMC2224 SoftwareSerial receive pin
#define SW_TX            8 // TMC2208/TMC2224 SoftwareSerial transmit pin
//#define SERIAL_PORT Serial1 // TMC2208/TMC2224 HardwareSerial port
#define DRIVER_ADDRESS 0b00 // TMC2209 Driver address according to MS1 and MS2

#define R_SENSE 0.11f // Match to your driver
                      // SilentStepStick series use 0.11
                      // UltiMachine Einsy and Archim2 boards use 0.2
                      // Panucatt BSD2660 uses 0.1
                      // Watterott TMC5160 uses 0.075


#define IDPIN_1           10 // Enable
#define IDPIN_2           16 // Enable

#include <AccelStepper.h>




TMC2209Stepper driver(SW_RX, SW_TX, R_SENSE, DRIVER_ADDRESS);
AccelStepper stepper = AccelStepper(stepper.DRIVER, STEP_PIN, DIR_PIN);



byte paramName = 0;
byte value1 = 0;
byte value2 = 0;
byte value3 = 0;
byte value4 = 0;
byte term = 0;

// for serial decode code
union u_tag {
   byte b[4];
   float fval;
} u;

float target_speed = 0;  // target speed








void setup() {
  pinMode(EN_PIN, OUTPUT);
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  

  Serial.begin (115200);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB
  }

  
  setupDriver();
}
void setupDriver(){
  digitalWrite(EN_PIN, LOW);      // Enable driver in hardware
  
  driver.beginSerial(115200);     // SW UART drivers

  driver.begin();                 //  SPI: Init CS pins and possible SW SPI pins
                                  // UART: Init SW UART (if selected) with default 115200 baudrate
  driver.toff(5);                 // Enables driver in software
  driver.rms_current(800);        // Set motor RMS current
  driver.microsteps(256);          // Set microsteps to 1/16th

//driver.en_pwm_mode(true);       // Toggle stealthChop on TMC2130/2160/5130/5160
  driver.en_spreadCycle(true);   // Toggle spreadCycle on TMC2208/2209/2224
  driver.pwm_autoscale(true);     // Needed for stealthChop

  stepper.setMaxSpeed(8000); // 
  stepper.setAcceleration(400); // 
  stepper.setEnablePin(EN_PIN);
  stepper.setPinsInverted(false, false, true);

  stepper.setSpeed(0);
  stepper.enableOutputs(); 
}

unsigned int skip = 0;
void loop() { 
  checkSerial();
  stepper.runSpeed();
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
      
     

      if(paramName == 'M'){
        driver.microsteps(int(u.fval));
        
      }else if (paramName == 'A'){  
        stepper.setMaxSpeed(u.fval);
        
      }else if (paramName == 'I'){  
        driver.rms_current(u.fval);


      }else if (paramName == 'R'){  
        setupDriver();
      }else if (paramName == 'G'){  
        stepper.setCurrentPosition(0);
       
      }else if (paramName == 'D'){  
        Serial.print(1); // COM8
        //Serial.print(0); // COM3
        Serial.print(stepper.currentPosition()); 
          
      }  
      else if (paramName == 'T'){  
        target_speed = u.fval;
        stepper.setSpeed(target_speed);

      }
      Serial.println("ok");
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
