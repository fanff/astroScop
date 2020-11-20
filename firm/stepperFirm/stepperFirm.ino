unsigned long time;

void setup() {
  // put your setup code here, to run once:
  pinMode(10, OUTPUT);
  pinMode(14, OUTPUT);
pinMode(13, OUTPUT);
  
  pinMode(15, OUTPUT);
  pinMode(16, OUTPUT);
}

int HL = 124;
void loop() {
  digitalWrite(15, HIGH); 
  
  digitalWrite(14, LOW); 
  digitalWrite(13, LOW); 
  delayMicroseconds(HL); 
    digitalWrite(14, HIGH); 
    digitalWrite(13, LOW); 
      delayMicroseconds(HL); 


}
