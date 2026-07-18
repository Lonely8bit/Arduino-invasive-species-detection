#include <SoftwareSerial.h>
#include <Servo.h> 

// --- PINS ---
const int enA = 10; const int in1 = 9; const int in2 = 8;  // Motor 1 (Right)
const int enB = 5;  const int in3 = 7; const int in4 = 6;  // Motor 2 (Left)
const int trigPin = 12; const int echoPin = 11; const int ledPin = 4; const int servoPin = A0; 

Servo myServo; 
SoftwareSerial btSerial(2, 3); // RX = 2, TX = 3

void setup() {
  pinMode(enA, OUTPUT); pinMode(enB, OUTPUT);
  pinMode(in1, OUTPUT); pinMode(in2, OUTPUT);
  pinMode(in3, OUTPUT); pinMode(in4, OUTPUT);
  pinMode(trigPin, OUTPUT); pinMode(echoPin, INPUT);
  pinMode(ledPin, OUTPUT);

  // Initial Servo Settle
  myServo.attach(servoPin); 
  myServo.write(90);        
  delay(500);               
  myServo.detach();         

  stop1(); stop2();
  turnLedOff();

  Serial.begin(9600);    
  btSerial.begin(9600);  
  btSerial.println("Robot Ready!");
}

void loop() {
  int distance = readDistanceCM();

  btSerial.print("Distance: ");
  btSerial.print(distance);
  btSerial.println(" cm");

  // OBSTACLE AVOIDANCE
  if (distance > 0 && distance < 15) {
    turnLedOn();
    stop1(); stop2(); 
    btSerial.println("Obstacle detected! Scanning...");

   // turnAndReturnServo(); 

    // [YOU CAN PLACE YOUR OWN MOTOR MOVEMENT CODING HERE!]

  } else {
    turnLedOff();
    forward1(255); forward2(255); // Both motors will now drive forward together
  }

  delay(100); 
}

// --- SERVO FUNCTION ---
void turnAndReturnServo() {
  myServo.attach(servoPin);    
  delay(50);                   
  myServo.write(10);          
  delay(600);                  
  myServo.write(90);           
  delay(600);                  
  myServo.detach();            
}

// --- MOTOR 1 FUNCTIONS (RIGHT) - INVERTED ---
void forward1(int speed)  { digitalWrite(in1, LOW);  digitalWrite(in2, HIGH); analogWrite(enA, speed); }
void backward1(int speed) { digitalWrite(in1, HIGH); digitalWrite(in2, LOW);  analogWrite(enA, speed); }
void stop1()              { digitalWrite(in1, LOW);  digitalWrite(in2, LOW);  analogWrite(enA, 0); }

// --- MOTOR 2 FUNCTIONS (LEFT) ---
void forward2(int speed)  { digitalWrite(in3, HIGH); digitalWrite(in4, LOW);  analogWrite(enB, speed); }
void backward2(int speed) { digitalWrite(in3, LOW);  digitalWrite(in4, HIGH); analogWrite(enB, speed); }
void stop2()              { digitalWrite(in3, LOW);  digitalWrite(in4, LOW);  analogWrite(enB, 0); }

// --- UTILITY FUNCTIONS ---
int readDistanceCM() {
  digitalWrite(trigPin, LOW); delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH);
  int distance = duration * 0.034 / 2;
  return (distance == 0) ? 100 : distance;
}

void turnLedOn()  { digitalWrite(ledPin, HIGH); }
void turnLedOff() { digitalWrite(ledPin, LOW); }
