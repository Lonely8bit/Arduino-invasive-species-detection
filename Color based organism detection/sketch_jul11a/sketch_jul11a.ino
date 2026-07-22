#include <Servo.h>

/*
  Species Detection & Action Controller - Main Receiver
  
  Expected Serial Format: "OSA\n" (3 digits + newline)
    - O: Organism ID (0 = None, 1 = Rat, 2 = Snail, 3 = Frog)
    - S: Section ID  (0 = None, 1 to 4)
    - A: Action Flag (0 = OFF, 1 = ON)

  Pin Assignment:
    - Servo 1 (Section 1): Pin 3
    - Servo 2 (Section 2): Pin 5
    - Servo 3 (Section 3): Pin 6
    - Servo 4 (Section 4): Pin 8
*/

// Create Servo objects
Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// Pin Definitions
const int SERVO1_PIN = 3;
const int SERVO2_PIN = 5;
const int SERVO3_PIN = 6;
const int SERVO4_PIN = 8;
const int ACTION_PIN = 13; // Built-in LED indicator for overall action state

// Memory state to prevent continuous re-triggering in the same section
int lastTriggeredSection = 0;

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50); // Low timeout to keep parsing responsive

  // Attach servos to the specified pins
  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);
  servo3.attach(SERVO3_PIN);
  servo4.attach(SERVO4_PIN);

  // Set initial home position to 0 degrees
  servo1.write(0);
  servo2.write(0);
  servo3.write(0);
  servo4.write(0);

  pinMode(ACTION_PIN, OUTPUT);
  digitalWrite(ACTION_PIN, LOW);
}

void loop() {
  // Check if serial data is available from Python
  if (Serial.available() > 0) {
    String inputString = Serial.readStringUntil('\n');
    inputString.trim(); // Clean trailing '\r' or whitespaces

    // Ensure we received a valid 3-digit packet
    if (inputString.length() == 3) {
      // Convert ASCII characters to integer values
      int organismID = inputString.charAt(0) - '0';
      int sectionID  = inputString.charAt(1) - '0';
      int actionFlag = inputString.charAt(2) - '0';

      // Update the onboard LED to show if the ACTION button is ON in Python
      digitalWrite(ACTION_PIN, actionFlag == 1 ? HIGH : LOW);

      // Trigger servo when Action is ON and a new section is detected
      if (actionFlag == 1 && sectionID > 0 && sectionID != lastTriggeredSection) {
        triggerSectionServo(sectionID);
        lastTriggeredSection = sectionID; 
      } 
      // Reset the state when the object leaves the screen or action is toggled OFF
      else if (sectionID == 0 || actionFlag == 0) {
        lastTriggeredSection = 0;
      }
    }
  }
}

// Function to move the corresponding servo: 0 -> 90 -> wait 0.6s -> 0
void triggerSectionServo(int section) {
  Servo *targetServo = NULL;

  switch (section) {
    case 1: targetServo = &servo1; break;
    case 2: targetServo = &servo2; break;
    case 3: targetServo = &servo3; break;
    case 4: targetServo = &servo4; break;
  }

  if (targetServo != NULL) {
    targetServo->write(90);  // Rotate to 90 degrees
    delay(600);              // Wait 0.6 seconds (600ms)
    targetServo->write(0);   // Return to 0 degrees
  }
}
