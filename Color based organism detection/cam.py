import cv2

def test_camera_indices(max_tested=10):
    print("=== Scanning Available Camera Indices ===")
    for index in range(max_tested):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) # CAP_DSHOW speeds up camera initialization on Windows
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"[FOUND] Index {index}: Camera working! Press 'q' on the window to check the next index.")
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    cv2.putText(frame, f"Camera Index: {index} (Press 'q' to close)", 
                                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.imshow(f"Camera Test Index {index}", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                cv2.destroyAllWindows()
            cap.release()
        else:
            print(f"[FAIL] Index {index}: No camera found.")

if __name__ == "__main__":
    test_camera_indices()