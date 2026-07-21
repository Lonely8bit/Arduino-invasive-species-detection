import cv2
import math
import time
import serial
from ultralytics import YOLO

# --- CONFIGURATION ---
IP_CAMERA_URL = "http://192.168.1.10:8080/video"

# Set your Serial Port (Windows: 'COM3', 'COM4' | Linux: '/dev/ttyUSB0', '/dev/ttyACM0')
SERIAL_PORT = '/dev/ttyUSB0'  
BAUD_RATE = 115200

# Connect to ESP32 over USB Serial
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Wait for serial reset
    print(f"[SUCCESS] Connected to ESP32 on {SERIAL_PORT}")
except Exception as e:
    print(f"[WARNING] Could not open Serial Port {SERIAL_PORT}. Test mode active (Terminal output only).")
    ser = None

# Load custom trained model (or fallback to yolov8n.pt if best.pt not found)
try:
    model = YOLO('runs/detect/train/weights/best.pt')
    TARGET_CLASSES = ['pen', 'keys', 'scissors']
    print("[INFO] Loaded custom trained model (best.pt)")
except:
    model = YOLO('yolov8n.pt')
    TARGET_CLASSES = ['scissors'] # Standard YOLOv8 has scissors built-in
    print("[INFO] Custom 'best.pt' not found. Fallback to standard yolov8n.pt")

poles = []
last_trigger_time = 0

def set_poles(event, x, y, flags, param):
    """Click mouse on live window to position 4 poles."""
    if event == cv2.EVENT_LBUTTONDOWN and len(poles) < 4:
        poles.append((x, y))
        print(f"Pole {len(poles)} set at: ({x}, {y})")

def calculate_closest_pole(obj_x, obj_y):
    closest_pole = -1
    min_dist = float('inf')
    for i, (px, py) in enumerate(poles):
        dist = math.hypot(px - obj_x, py - obj_y)
        if dist < min_dist:
            min_dist = dist
            closest_pole = i + 1  # Pole 1, 2, 3, or 4
    return closest_pole

cap = cv2.VideoCapture(IP_CAMERA_URL)
cv2.namedWindow("Targeting System")
cv2.setMouseCallback("Targeting System", set_poles)

print("\n--- DETECTOR READY ---")
print("1. Click 4 points on the camera feed to place Pole 1, Pole 2, Pole 3, Pole 4.")
print("2. Press 'r' to reset pole markers.")
print("3. Press 'q' to quit.\n")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    results = model(frame, stream=True, verbose=False)

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            class_name = model.names[cls_id]

            if class_name in TARGET_CLASSES:
                x1, y1, x2, y2 = box.xyxy[0].int().tolist()
                center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2

                # Draw bounding box & object center dot
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, class_name.upper(), (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

                if len(poles) == 4:
                    closest_pole = calculate_closest_pole(center_x, center_y)
                    
                    # Display targeted pole on screen
                    cv2.putText(frame, f"TARGET -> POLE {closest_pole}", (30, 50), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

                    # Cooldown rate limit (send command once every 2 seconds)
                    if time.time() - last_trigger_time > 2.0:
                        # Command string format
                        command_str = f"POLE:{closest_pole},TARGET:{class_name}\n"

                        # 1. PRINT TO PC TERMINAL
                        print(f"[PC TERMINAL OUTPUT] Command: {command_str.strip()}")

                        # 2. SEND OVER USB SERIAL TO ESP32
                        if ser and ser.is_open:
                            ser.write(command_str.encode('utf-8'))

                        last_trigger_time = time.time()

    # Draw poles on camera feed
    for i, (px, py) in enumerate(poles):
        cv2.circle(frame, (px, py), 10, (255, 0, 0), -1)
        cv2.putText(frame, f"P{i+1}", (px + 15, py - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    cv2.imshow("Targeting System", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        poles.clear()
        print("Poles reset.")

cap.release()
cv2.destroyAllWindows()
if ser:
    ser.close()