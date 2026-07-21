import os
import cv2
import yaml
import time
from ultralytics import YOLO

# --- CONFIGURATION ---
IP_CAMERA_URL = "http://192.168.1.10:8080/video"  # Update with your phone's IP
DATASET_DIR = "custom_dataset"

IMG_DIR = os.path.join(DATASET_DIR, "images", "train")
LBL_DIR = os.path.join(DATASET_DIR, "labels", "train")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(LBL_DIR, exist_ok=True)

drawing = False
ix, iy, fx, fy = -1, -1, -1, -1
box_drawn = False

def draw_rectangle(event, x, y, flags, param):
    global drawing, ix, iy, fx, fy, box_drawn
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        box_drawn = False
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        fx, fy = x, y
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        fx, fy = x, y
        box_drawn = True

def convert_to_yolo_bbox(img_w, img_h, x1, y1, x2, y2):
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)
    return (((xmin + xmax) / 2.0) / img_w, 
            ((ymin + ymax) / 2.0) / img_h, 
            (xmax - xmin) / img_w, 
            (ymax - ymin) / img_h)

cap = cv2.VideoCapture(IP_CAMERA_URL)
cv2.namedWindow("Object Annotator")
cv2.setMouseCallback("Object Annotator", draw_rectangle)

classes = ['pen', 'keys', 'scissors']
image_count = 0

print("\n--- TRAINER INSTRUCTIONS ---")
print("1. Point camera at a Pen, Keys, or Scissors.")
print("2. Click & drag a box over the object.")
print("3. Press 's' to save and enter class ID (0=pen, 1=keys, 2=scissors).")
print("4. Repeat 10-15 times per object.")
print("5. Press 't' to start local AI training!\n")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    display_frame = frame.copy()
    img_h, img_w, _ = frame.shape

    if (drawing or box_drawn) and ix != -1:
        cv2.rectangle(display_frame, (ix, iy), (fx, fy), (0, 255, 0), 2)

    cv2.putText(display_frame, f"Saved: {image_count} | Classes: 0:pen, 1:keys, 2:scissors", 
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.putText(display_frame, "[S]: Save Box | [T]: Train | [Q]: Quit", 
                (20, img_h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("Object Annotator", display_frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s') and box_drawn:
        class_str = input("Enter Class ID (0 for pen, 1 for keys, 2 for scissors): ").strip()
        if class_str in ['0', '1', '2']:
            class_id = int(class_str)
            filename = f"img_{int(time.time()*1000)}"
            
            cv2.imwrite(os.path.join(IMG_DIR, f"{filename}.jpg"), frame)
            
            xc, yc, w, h = convert_to_yolo_bbox(img_w, img_h, ix, iy, fx, fy)
            with open(os.path.join(LBL_DIR, f"{filename}.txt"), "w") as f:
                f.write(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")

            image_count += 1
            box_drawn = False
            ix, iy, fx, fy = -1, -1, -1, -1
            print(f"--> Saved {classes[class_id]} image ({image_count} total)")

    elif key == ord('t'):
        if image_count == 0:
            print("Collect some images first!")
            continue
        break
    elif key == ord('q'):
        cap.release()
        cv2.destroyAllWindows()
        exit()

cap.release()
cv2.destroyAllWindows()

# Generate YAML config and train
yaml_path = os.path.join(DATASET_DIR, "data.yaml")
with open(yaml_path, 'w') as f:
    yaml.dump({
        'path': os.path.abspath(DATASET_DIR),
        'train': 'images/train',
        'val': 'images/train',
        'names': {i: name for i, name in enumerate(classes)}
    }, f)

print("\nTraining local YOLO model...")
model = YOLO('yolov8n.pt')
model.train(data=yaml_path, epochs=35, imgsz=640)
print("\nTraining Complete! 'best.pt' generated successfully.\n")