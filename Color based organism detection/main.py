import cv2
import numpy as np
import serial
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

# ==========================================
# EASY CONFIGURATION VARIABLES
# ==========================================
CAMERA_INDEX = 0        # Set your DroidCam USB index here
COM_PORT = 'COM3'       # Set your Arduino COM port here (e.g., 'COM3' or '/dev/ttyUSB0')
BAUD_RATE = 9600
# ==========================================

class ObjectDetectionApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Species Detection & Action Controller")
        
        # Serial Setup
        self.ser = None
        try:
            self.ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
            time.sleep(2)
            print(f"Connected to Serial Port: {COM_PORT}")
        except Exception as e:
            print(f"Warning: Serial connection failed ({e}). Running in offline mode.")

        # Camera Setup
        self.cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        
        # Current processed BGR frame storage for click sampling
        self.current_frame = None

        # Toggle action flag & Calibrator visibility state
        self.action_triggered = False
        self.show_calibrator = False
        self.is_loading_sliders = False
        self.last_send_time = time.time()

        # HSV Color Ranges (Lower, Upper)
        self.color_ranges = {
            'Pink Bottle': {
                'id': 1,
                'color_bgr': (180, 105, 255), # Bright Pink bounding box
                'lower': np.array([130, 30, 40]),
                'upper': np.array([175, 255, 255])
            },
            'Green': {
                'id': 4,
                'color_bgr': (0, 255, 0),     # Green bounding box
                'lower': np.array([35, 80, 50]),
                'upper': np.array([80, 255, 255])
            },
            'Rat': {
                'id': 2,
                'color_bgr': (255, 255, 255), # White bounding box
                'lower': np.array([0, 0, 180]),
                'upper': np.array([180, 50, 255])
            },
            'Frog': {
                'id': 3,
                'color_bgr': (255, 0, 0),     # Blue bounding box
                'lower': np.array([90, 80, 80]),
                'upper': np.array([130, 255, 255])
            }
        }

        # Setup GUI Elements
        self.setup_gui()

    def setup_gui(self):
        # 1. Main Content Frame (Side-by-Side: Video on Left, Status Panel on Right)
        content_frame = ttk.Frame(self.window)
        content_frame.pack(side=tk.TOP, padx=10, pady=5)

        # Video Display Canvas with Click Event Binding
        self.canvas = tk.Canvas(content_frame, width=640, height=480, cursor="crosshair")
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Right-side Panel for Large Detection Indicator (Outside Video Frame)
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        ttk.Label(right_panel, text="DETECTION STATUS", font=("Arial", 11, "bold")).pack(pady=(0, 5))

        self.detection_display_label = tk.Label(
            right_panel, 
            text="NOT\nDETECTED", 
            bg="#D32F2F", 
            fg="white", 
            font=("Arial", 14, "bold"),
            width=16,
            height=8,
            relief=tk.RAISED
        )
        self.detection_display_label.pack(fill=tk.BOTH, expand=True)

        # 2. Main Control Bar Frame
        control_frame = ttk.Frame(self.window)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Toggle "ACTION" Button
        self.btn_action = tk.Button(
            control_frame, 
            text="ACTION: OFF", 
            bg="#D32F2F", 
            fg="white", 
            activebackground="#9A0007",
            activeforeground="white",
            font=("Arial", 11, "bold"),
            command=self.trigger_action
        )
        self.btn_action.pack(side=tk.LEFT, padx=5)

        # "CALIBRATOR" Toggle Button
        self.btn_calib_toggle = tk.Button(
            control_frame,
            text="SHOW CALIBRATOR",
            bg="#1976D2",
            fg="white",
            activebackground="#0D47A1",
            activeforeground="white",
            font=("Arial", 11, "bold"),
            command=self.toggle_calibrator
        )
        self.btn_calib_toggle.pack(side=tk.LEFT, padx=5)

        # Status Label
        self.status_label = ttk.Label(control_frame, text="Status: Initializing...", font=("Arial", 10))
        self.status_label.pack(side=tk.LEFT, padx=15)

        # 3. Hidden Calibration Panel Frame
        self.calib_frame = ttk.LabelFrame(self.window, text=" HSV Color Calibrator ")
        self.setup_calibration_panel()

        # Start Video Loop
        self.update_frame()

    def setup_calibration_panel(self):
        # Organism Selector Dropdown
        top_row = ttk.Frame(self.calib_frame)
        top_row.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(top_row, text="Select Target: ", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.species_var = tk.StringVar(value='Pink Bottle')
        self.species_combo = ttk.Combobox(
            top_row, 
            textvariable=self.species_var, 
            values=list(self.color_ranges.keys()), 
            state="readonly",
            width=15
        )
        self.species_combo.pack(side=tk.LEFT, padx=5)
        self.species_combo.bind("<<ComboboxSelected>>", self.load_sliders_from_species)

        ttk.Label(top_row, text="(Tip: Click object on video feed to auto-sample color)", font=("Arial", 9, "italic"), foreground="gray").pack(side=tk.LEFT, padx=10)

        # Sliders Grid Container
        grid_frame = ttk.Frame(self.calib_frame)
        grid_frame.pack(fill=tk.X, padx=10, pady=5)

        self.sliders = {}
        slider_configs = [
            ("Lower Hue", "lh", 0, 179),
            ("Upper Hue", "uh", 0, 179),
            ("Lower Saturation", "ls", 0, 255),
            ("Upper Saturation", "us", 0, 255),
            ("Lower Value (Brightness)", "lv", 0, 255),
            ("Upper Value (Brightness)", "uv", 0, 255),
        ]

        for idx, (label_text, key, min_val, max_val) in enumerate(slider_configs):
            row = idx // 2
            col = (idx % 2) * 2

            ttk.Label(grid_frame, text=f"{label_text}:", font=("Arial", 9)).grid(row=row, column=col, sticky="w", padx=5, pady=2)
            
            slider = tk.Scale(
                grid_frame, 
                from_=min_val, 
                to=max_val, 
                orient=tk.HORIZONTAL, 
                length=180,
                command=lambda val, k=key: self.on_slider_change(k, val)
            )
            slider.grid(row=row, column=col+1, padx=5, pady=2)
            self.sliders[key] = slider

        # RGB Text Labels & Color Preview Boxes
        preview_frame = ttk.Frame(self.calib_frame)
        preview_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(preview_frame, text="Lower RGB: ", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_lower_rgb = ttk.Label(preview_frame, text="(0, 0, 0)", width=12)
        self.lbl_lower_rgb.pack(side=tk.LEFT)
        self.box_lower = tk.Canvas(preview_frame, width=25, height=25, bg="black", highlightbackground="gray", highlightthickness=1)
        self.box_lower.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(preview_frame, text="Upper RGB: ", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_upper_rgb = ttk.Label(preview_frame, text="(255, 255, 255)", width=12)
        self.lbl_upper_rgb.pack(side=tk.LEFT)
        self.box_upper = tk.Canvas(preview_frame, width=25, height=25, bg="white", highlightbackground="gray", highlightthickness=1)
        self.box_upper.pack(side=tk.LEFT)

        self.load_sliders_from_species()

    def on_canvas_click(self, event):
        """Samples HSV value where the user clicks on the video canvas."""
        if self.current_frame is None:
            return

        x, y = event.x, event.y
        h, w, _ = self.current_frame.shape

        if 0 <= x < w and 0 <= y < h:
            x_min, x_max = max(0, x - 2), min(w, x + 3)
            y_min, y_max = max(0, y - 2), min(h, y + 3)
            
            roi = self.current_frame[y_min:y_max, x_min:x_max]
            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            avg_hsv = np.mean(roi_hsv, axis=(0, 1)).astype(int)

            h_val, s_val, v_val = avg_hsv[0], avg_hsv[1], avg_hsv[2]

            lh = max(0, h_val - 12)
            uh = min(179, h_val + 12)
            ls = max(30, s_val - 60)
            us = min(255, s_val + 60)
            lv = max(30, v_val - 60)
            uv = min(255, v_val + 60)

            self.sliders['lh'].set(lh)
            self.sliders['uh'].set(uh)
            self.sliders['ls'].set(ls)
            self.sliders['us'].set(us)
            self.sliders['lv'].set(lv)
            self.sliders['uv'].set(uv)

            self.on_slider_change(None, None)
            
            if not self.show_calibrator:
                self.toggle_calibrator()

    def toggle_calibrator(self):
        self.show_calibrator = not self.show_calibrator
        if self.show_calibrator:
            self.calib_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
            self.btn_calib_toggle.config(text="HIDE CALIBRATOR", bg="#455A64")
        else:
            self.calib_frame.pack_forget()
            self.btn_calib_toggle.config(text="SHOW CALIBRATOR", bg="#1976D2")

    def load_sliders_from_species(self, event=None):
        self.is_loading_sliders = True
        species = self.species_var.get()
        lower = self.color_ranges[species]['lower']
        upper = self.color_ranges[species]['upper']

        self.sliders['lh'].set(lower[0])
        self.sliders['ls'].set(lower[1])
        self.sliders['lv'].set(lower[2])

        self.sliders['uh'].set(upper[0])
        self.sliders['us'].set(upper[1])
        self.sliders['uv'].set(upper[2])
        self.is_loading_sliders = False
        
        self.update_color_previews()

    def on_slider_change(self, key, value):
        if self.is_loading_sliders:
            return
        
        species = self.species_var.get()
        lh = self.sliders['lh'].get()
        ls = self.sliders['ls'].get()
        lv = self.sliders['lv'].get()

        uh = self.sliders['uh'].get()
        us = self.sliders['us'].get()
        uv = self.sliders['uv'].get()

        self.color_ranges[species]['lower'] = np.array([lh, ls, lv])
        self.color_ranges[species]['upper'] = np.array([uh, us, uv])
        
        self.update_color_previews()

    def update_color_previews(self):
        lh, ls, lv = self.sliders['lh'].get(), self.sliders['ls'].get(), self.sliders['lv'].get()
        uh, us, uv = self.sliders['uh'].get(), self.sliders['us'].get(), self.sliders['uv'].get()

        lower_hsv_pixel = np.uint8([[[lh, ls, lv]]])
        upper_hsv_pixel = np.uint8([[[uh, us, uv]]])

        lower_rgb = cv2.cvtColor(lower_hsv_pixel, cv2.COLOR_HSV2RGB)[0][0]
        upper_rgb = cv2.cvtColor(upper_hsv_pixel, cv2.COLOR_HSV2RGB)[0][0]

        lower_hex = f"#{lower_rgb[0]:02x}{lower_rgb[1]:02x}{lower_rgb[2]:02x}"
        upper_hex = f"#{upper_rgb[0]:02x}{upper_rgb[1]:02x}{upper_rgb[2]:02x}"

        self.lbl_lower_rgb.config(text=f"({lower_rgb[0]}, {lower_rgb[1]}, {lower_rgb[2]})")
        self.lbl_upper_rgb.config(text=f"({upper_rgb[0]}, {upper_rgb[1]}, {upper_rgb[2]})")

        self.box_lower.config(bg=lower_hex)
        self.box_upper.config(bg=upper_hex)

    def trigger_action(self):
        self.action_triggered = not self.action_triggered
        if self.action_triggered:
            self.btn_action.config(
                text="ACTION: ON", 
                bg="#2E7D32", 
                activebackground="#1B5E20"
            )
        else:
            self.btn_action.config(
                text="ACTION: OFF", 
                bg="#D32F2F", 
                activebackground="#9A0007"
            )

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.window.after(30, self.update_frame)
            return

        frame = cv2.resize(frame, (640, 480))
        self.current_frame = frame.copy()
        h, w, _ = frame.shape

        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # Draw 4 Vertical Sections
        sec_width = w // 4
        for i in range(1, 4):
            cv2.line(frame, (i * sec_width, 0), (i * sec_width, h), (0, 255, 255), 2)
            cv2.putText(frame, f"Sec {i}", (i * sec_width - sec_width + 10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, "Sec 4", (3 * sec_width + 10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        detected_organism_id = 0
        detected_section_id = 0
        detected_name = "None"

        kernel = np.ones((5, 5), np.uint8)

        for name, spec in self.color_ranges.items():
            mask = cv2.inRange(hsv, spec['lower'], spec['upper'])
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                if cv2.contourArea(cnt) > 200:  # Set low to catch bottle caps/small objects
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    cx = x + bw // 2
                    
                    section = (cx // sec_width) + 1
                    section = min(max(section, 1), 4)

                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), spec['color_bgr'], 2)
                    cv2.putText(frame, f"{name} (Sec {section})", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, spec['color_bgr'], 2)

                    detected_organism_id = spec['id']
                    detected_section_id = section
                    detected_name = name
                    break 

        # ==========================================
        # RIGHT-SIDE STATUS PANEL UPDATE
        # ==========================================
        if detected_organism_id != 0:
            status_text = f"{detected_name.upper()}\nDETECTED\n\n(SEC {detected_section_id})"
            self.detection_display_label.config(text=status_text, bg="#2E7D32") # Green
        else:
            status_text = "NOT\nDETECTED"
            self.detection_display_label.config(text=status_text, bg="#D32F2F") # Red

        action_flag = 1 if self.action_triggered else 0
        serial_code = f"{detected_organism_id}{detected_section_id}{action_flag}"

        if time.time() - self.last_send_time > 0.2:
            if self.ser and self.ser.is_open:
                self.ser.write((serial_code + '\n').encode('utf-8'))
            self.last_send_time = time.time()

        detected_label_status = f"{detected_name} in Sec {detected_section_id}" if detected_organism_id != 0 else "None"
        self.status_label.config(text=f"Detected: {detected_label_status} | Code Sent: {serial_code}")

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(image=img_pil)
        
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.canvas.image = img_tk

        self.window.after(30, self.update_frame)

    def on_closing(self):
        if self.cap.isOpened():
            self.cap.release()
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ObjectDetectionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()