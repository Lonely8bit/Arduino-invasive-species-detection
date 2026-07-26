#include <Servo.h>

/*
  Species Detection & Action Controller - Main Receiver (No Bluetooth)
  
  Expected Serial Format: "OSA\n" (3 digits + newline)
    - O: Organism ID (0 = None, 1 = Rat, etc.)
    - S: Section ID  (0 = None, 1 to 4)
    - A: Action Flag (0 = OFF, 1 = ON)

  Pin Assignments:
    - Servos:  Pin 3 (Sec 1), Pin 5 (Sec 2), Pin 6 (Sec 3), Pin 8 (Sec 4)
    - LEDs:    Pin 2 (LED 1), Pin 4 (LED 2), Pin 7 (LED 3), Pin 9 (LED 4)
    - Buzzer:  Pin 12
    - Action:  Pin 13 (Built-in LED)
*/

// Create Servo objects
Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// Pin Definitions - Servos
const int SERVO1_PIN = 3;
const int SERVO2_PIN = 5;
const int SERVO3_PIN = 6;
const int SERVO4_PIN = 8;

// Pin Definitions - LEDs
const int LED1_PIN = 2;
const int LED2_PIN = 4;
const int LED3_PIN = 7;
const int LED4_PIN = 9;

// Pin Definitions - Buzzer & Action State
const int BUZZER_PIN = 12;
const int ACTION_PIN = 13; 

// Memory state to prevent continuous re-triggering
int lastTriggeredSection = 0;

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50); // Fast timeout for responsive Python communication

  // Configure LED pins
  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);
  pinMode(LED3_PIN, OUTPUT);
  pinMode(LED4_PIN, OUTPUT);

  // Configure Buzzer & Action pins
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(ACTION_PIN, OUTPUT);

  // Turn everything OFF initially
  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);
  digitalWrite(LED3_PIN, LOW);
  digitalWrite(LED4_PIN, LOW);
  noTone(BUZZER_PIN);
  digitalWrite(ACTION_PIN, LOW);

  // Jitter Fix: Attach, move to 10 degrees (not 0), wait, then detach
  servo1.attach(SERVO1_PIN); servo1.write(10);
  servo2.attach(SERVO2_PIN); servo2.write(10);
  servo3.attach(SERVO3_PIN); servo3.write(10);
  servo4.attach(SERVO4_PIN); servo4.write(10);
  delay(500); // Give servos time to reach home position
  servo1.detach();
  servo2.detach();
  servo3.detach();
  servo4.detach();
}

void loop() {
  // Check if serial data is available from Python
  if (Serial.available() > 0) {
    String inputString = "";

    // CRITICAL FIX: Flush out the backlog of old commands!
    // Since the servos use delay(), Python sends many commands while Arduino sleeps.
    // This loop forces the Arduino to skip the old ones and read only the most recent status.
    while (Serial.available() > 0) {
      String temp = Serial.readStringUntil('\n');
      temp.trim(); 
      if (temp.length() == 3) {
        inputString = temp;
      }
    }

    // Ensure we received a valid 3-digit packet
    if (inputString.length() == 3) {
      int organismID = inputString.charAt(0) - '0';
      int sectionID  = inputString.charAt(1) - '0';
      int actionFlag = inputString.charAt(2) - '0';

      // Update the onboard Action LED
      digitalWrite(ACTION_PIN, actionFlag == 1 ? HIGH : LOW);

      // Update Section LEDs and Buzzer IMMEDIATELY based on current status
      updateSectionOutputs(sectionID);

      // Trigger servo when Action is ON and a new section is detected
      if (actionFlag == 1 && sectionID > 0 && sectionID != lastTriggeredSection) {
        triggerSectionServo(sectionID);
        lastTriggeredSection = sectionID; 

        // CRITICAL FIX 2: Ensure the buzzer and LED shut off immediately 
        // after the servo finishes, stopping them from getting "stuck" on.
        updateSectionOutputs(0); 
      } 
      // Reset the state when object leaves screen or action is toggled OFF
      else if (sectionID == 0 || actionFlag == 0) {
        lastTriggeredSection = 0;
      }
    }
  }
}

// Function to handle LEDs and Buzzer based on detected Section
void updateSectionOutputs(int section) {
  // Always turn off all LEDs and stop Buzzer FIRST
  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);
  digitalWrite(LED3_PIN, LOW);
  digitalWrite(LED4_PIN, LOW);
  noTone(BUZZER_PIN);

  // If a section is active, turn ON specific LED and play tone
  switch (section) {
    case 1: digitalWrite(LED1_PIN, HIGH); tone(BUZZER_PIN, 2000); break;
    case 2: digitalWrite(LED2_PIN, HIGH); tone(BUZZER_PIN, 2000); break;
    case 3: digitalWrite(LED3_PIN, HIGH); tone(BUZZER_PIN, 2000); break;
    case 4: digitalWrite(LED4_PIN, HIGH); tone(BUZZER_PIN, 2000); break;
  }
}

// Function to move servo (Anti-Jitter version)
void triggerSectionServo(int section) {
  Servo *targetServo = NULL;
  int pin = 0;

  switch (section) {
    case 1: targetServo = &servo1; pin = SERVO1_PIN; break;
    case 2: targetServo = &servo2; pin = SERVO2_PIN; break;
    case 3: targetServo = &servo3; pin = SERVO3_PIN; break;
    case 4: targetServo = &servo4; pin = SERVO4_PIN; break;
  }

  if (targetServo != NULL) {
    targetServo->attach(pin);  // Re-attach to send signal
    targetServo->write(90);    // Rotate to 90 degrees
    delay(600);                // Wait 0.6 seconds
    targetServo->write(10);    // Return to 10 degrees (avoids end-stop strain)
    delay(300);                // Give it time to travel back
    targetServo->detach();     // Detach to stop signal and prevent jitter
  }
}
