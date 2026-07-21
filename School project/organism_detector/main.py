import cv2
import numpy as np
import os
import serial
import time

# ==================== CONFIGURATION ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REF_FOLDER = os.path.join(SCRIPT_DIR, "ref_images")

MIN_INLIERS = 18       
RATIO_THRESHOLD = 0.68 

DROIDCAM_WIFI_URL = "http://192.168.1.15:4747/video"
SERIAL_PORT = 'COM3'  # Update to match your ESP32 COM port
BAUD_RATE = 115200

# Strict mapping to ensure Python and ESP32 agree on IDs
ORGANISM_MAP = {
    "beetle": 1,
    "rat": 2,
    "frog": 3,
    "lantana": 4,
    "snail": 5,
    "pink_morning": 6
}

BUTTON_BOX = (20, 20, 180, 70)
button_clicked = False
# =======================================================


def mouse_callback(event, x, y, flags, param):
    global button_clicked
    if event == cv2.EVENT_LBUTTONDOWN:
        x1, y1, x2, y2 = BUTTON_BOX
        if x1 <= x <= x2 and y1 <= y <= y2:
            button_clicked = True


def connect_droidcam():
    print("--- Searching for DroidCam USB Stream ---")
    for idx in [1, 0, 2]:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f" Connected to USB DroidCam at index {idx}!\n")
                return cap
        cap.release()

    print(f"Trying Wi-Fi URL: {DROIDCAM_WIFI_URL}")
    cap = cv2.VideoCapture(DROIDCAM_WIFI_URL)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            return cap
    return None


def load_reference_descriptors(sift):
    ref_data = {}
    if not os.path.exists(REF_FOLDER):
        return ref_data

    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    files = [f for f in os.listdir(REF_FOLDER) if f.lower().endswith(valid_extensions)]

    print("--- Organism ID Mapping ---")
    for filename in files:
        filepath = os.path.join(REF_FOLDER, filename)
        raw_name = os.path.splitext(filename)[0].lower()
        
        if raw_name not in ORGANISM_MAP:
            print(f" [SKIP] '{filename}' not in ORGANISM_MAP. Rename it.")
            continue

        org_id = ORGANISM_MAP[raw_name]
        display_name = raw_name.replace('_', ' ').title()

        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        h, w = img.shape
        kp, des = sift.detectAndCompute(img, None)
        if des is not None and len(kp) > 0:
            ref_data[display_name] = {'id': org_id, 'kp': kp, 'des': des, 'w': w, 'h': h}
            print(f" ID {org_id} -> {display_name}")
    print("---------------------------\n")
    return ref_data


def main():
    global button_clicked
    esp32 = None
    try:
        esp32 = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"--- Connected to ESP32 on {SERIAL_PORT} ---")
        time.sleep(2)
    except serial.SerialException:
        print(f"\n[WARNING] Could not connect to ESP32 on {SERIAL_PORT}. Running vision only.\n")

    sift = cv2.SIFT_create()
    bf = cv2.BFMatcher(cv2.NORM_L2)
    ref_descriptors = load_reference_descriptors(sift)
    cap = connect_droidcam()

    if not ref_descriptors or cap is None:
        return

    window_name = "Invasive Species Detector"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)

    last_sent_payload = None
    current_active_section = None

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        height, width, _ = frame.shape
        sec_width = width / 4.0

        for i in range(1, 4):
            x_pos = int(i * sec_width)
            cv2.line(frame, (x_pos, 0), (x_pos, height), (0, 255, 255), 2)

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp_frame, des_frame = sift.detectAndCompute(gray_frame, None)

        best_organism = None
        max_inliers = 0
        best_card_box = None
        best_centroid = None

        if des_frame is not None and len(des_frame) > 0:
            for name, data in ref_descriptors.items():
                matches = bf.knnMatch(data['des'], des_frame, k=2)
                good_matches = [m for m, n in matches if m.distance < RATIO_THRESHOLD * n.distance]

                if len(good_matches) >= MIN_INLIERS:
                    src_pts = np.float32([data['kp'][m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                    dst_pts = np.float32([kp_frame[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

                    if M is not None and mask is not None:
                        inliers_count = int(np.sum(mask))
                        if inliers_count >= MIN_INLIERS and inliers_count > max_inliers:
                            h_ref, w_ref = data['h'], data['w']
                            pts_ref = np.float32([[0, 0], [0, h_ref - 1], [w_ref - 1, h_ref - 1], [w_ref - 1, 0]]).reshape(-1, 1, 2)
                            dst_corners = cv2.perspectiveTransform(pts_ref, M)

                            area = cv2.contourArea(dst_corners)
                            if 1500 < area < (width * height * 0.85):
                                cx = float(np.mean(dst_corners[:, 0, 0]))
                                cy = float(np.mean(dst_corners[:, 0, 1]))
                                max_inliers = inliers_count
                                best_organism = name
                                best_card_box = np.int32(dst_corners)
                                best_centroid = (cx, cy)

        if best_organism and best_centroid and best_card_box is not None:
            cx, cy = best_centroid
            section_number = int(cx // sec_width) + 1
            section_number = max(1, min(4, section_number))
            current_active_section = section_number
            org_id = ref_descriptors[best_organism]['id']

            payload = f"{org_id}{section_number}\n"

            if payload != last_sent_payload:
                print(f"[DETECTED] {best_organism} | Section {section_number} | Sending: {payload.strip()}")
                if esp32 and esp32.is_open:
                    esp32.write(payload.encode('utf-8'))
                last_sent_payload = payload

            cv2.polylines(frame, [best_card_box], True, (0, 255, 0), 3)
            cv2.putText(frame, f"{best_organism} (Sec {section_number})", (int(cx) - 60, int(cy) - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            current_active_section = None
            if last_sent_payload != "00\n":
                if esp32 and esp32.is_open:
                    esp32.write(b"00\n")
                last_sent_payload = "00\n"

        # Action Button
        bx1, by1, bx2, by2 = BUTTON_BOX
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 200), -1)
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 255, 255), 2)
        cv2.putText(frame, "TAKE ACTION", (bx1 + 12, by1 + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        key = cv2.waitKey(1) & 0xFF
        if button_clicked or key == ord(' '):
            button_clicked = False
            if current_active_section is not None:
                action_cmd = f"9{current_active_section}\n"
                print(f"[ACTION] Triggering Servo Pole {current_active_section} -> Sending: {action_cmd.strip()}")
                if esp32 and esp32.is_open:
                    esp32.write(action_cmd.encode('utf-8'))
            else:
                print("[ACTION] No organism detected on screen to act upon.")

        cv2.imshow(window_name, frame)
        if key == ord('q'):
            break

    if esp32 and esp32.is_open:
        esp32.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()