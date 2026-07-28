import cv2
import numpy as np
import serial
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# ==========================================
# EASY CONFIGURATION VARIABLES
# ==========================================
CAMERA_INDEX = 2        # Set your DroidCam USB index here
COM_PORT = 'COM7'       # Set your Arduino COM port here (e.g., 'COM3' or '/dev/ttyUSB0')
BAUD_RATE = 9600
# ==========================================

class ObjectDetectionApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Species Detection & Action Controller")
        
        # Safe Serial Setup (Works even if COM port is missing or fails)
        self.ser = None
        try:
            self.ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
            time.sleep(1)
            print(f"Connected to Serial Port: {COM_PORT}")
        except Exception as e:
            print(f"Warning: Serial connection failed ({e}). Running in offline mode.")
            self.ser = None

        # Camera Setup
        self.cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        
        # Current processed BGR frame storage
        self.current_frame = None

        # State Variables
        self.action_triggered = False
        self.show_calibrator = False
        self.edit_sections_mode = False
        self.selected_node = None  # Stores (sec_id, pt_index) during drag
        self.is_loading_sliders = False
        self.last_send_time = time.time()

        # Editable Closed Curves (4 Section Polygons: [x, y] vertex coordinates)
        self.sections = {
            1: [[10, 10], [150, 10], [150, 470], [10, 470]],
            2: [[170, 10], [310, 10], [310, 470], [170, 470]],
            3: [[330, 10], [470, 10], [470, 470], [330, 470]],
            4: [[490, 10], [630, 10], [630, 470], [490, 470]],
        }

        # HSV Color Ranges (Lower, Upper) + Active Toggle State
        self.color_ranges = {
            'Pink Bottle': {
                'id': 1,
                'color_bgr': (180, 105, 255),
                'lower': np.array([130, 30, 40]),
                'upper': np.array([175, 255, 255]),
                'enabled': True
            },
            'Green': {
                'id': 4,
                'color_bgr': (0, 255, 0),
                'lower': np.array([35, 80, 50]),
                'upper': np.array([80, 255, 255]),
                'enabled': True
            },
            'Rat': {
                'id': 2,
                'color_bgr': (255, 255, 255),
                'lower': np.array([0, 0, 180]),
                'upper': np.array([180, 50, 255]),
                'enabled': True
            },
            'Frog': {
                'id': 3,
                'color_bgr': (255, 0, 0),
                'lower': np.array([90, 80, 80]),
                'upper': np.array([130, 255, 255]),
                'enabled': True
            }
        }

        # Setup GUI
        self.setup_gui()

    def setup_gui(self):
        # 1. Main Content Frame (Video on Left, Status Panel on Right)
        content_frame = ttk.Frame(self.window)
        content_frame.pack(side=tk.TOP, padx=10, pady=5)

        # Video Display Canvas with Interactive Canvas Mouse Events
        self.canvas = tk.Canvas(content_frame, width=640, height=480, cursor="crosshair")
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Right-side Panel for Detection Indicator
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
            font=("Arial", 10, "bold"),
            command=self.trigger_action
        )
        self.btn_action.pack(side=tk.LEFT, padx=3)

        # Toggle "EDIT ZONES" Button
        self.btn_edit_zones = tk.Button(
            control_frame,
            text="EDIT ZONES: OFF",
            bg="#E65100",
            fg="white",
            activebackground="#B23C00",
            activeforeground="white",
            font=("Arial", 10, "bold"),
            command=self.toggle_edit_zones
        )
        self.btn_edit_zones.pack(side=tk.LEFT, padx=3)

        # "CALIBRATOR" Toggle Button
        self.btn_calib_toggle = tk.Button(
            control_frame,
            text="SHOW CALIBRATOR",
            bg="#1976D2",
            fg="white",
            activebackground="#0D47A1",
            activeforeground="white",
            font=("Arial", 10, "bold"),
            command=self.toggle_calibrator
        )
        self.btn_calib_toggle.pack(side=tk.LEFT, padx=3)

        # Status Label
        self.status_label = ttk.Label(control_frame, text="Status: Initializing...", font=("Arial", 9))
        self.status_label.pack(side=tk.LEFT, padx=10)

        # 3. Hidden Calibration Panel Frame
        self.calib_frame = ttk.LabelFrame(self.window, text=" HSV Color & Target Calibrator ")
        self.setup_calibration_panel()

        # Start Video Loop
        self.update_frame()

    def setup_calibration_panel(self):
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

        self.species_enabled_var = tk.BooleanVar(value=True)
        self.chk_enabled = ttk.Checkbutton(
            top_row,
            text="Enable Detection",
            variable=self.species_enabled_var,
            command=self.on_enable_toggle
        )
        self.chk_enabled.pack(side=tk.LEFT, padx=15)

        ttk.Label(top_row, text="(Tip: Click video to auto-sample color when Edit Zones is OFF)", font=("Arial", 9, "italic"), foreground="gray").pack(side=tk.LEFT, padx=5)

        edit_row = ttk.Frame(self.calib_frame)
        edit_row.pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(edit_row, text="Rename Selected Target: ", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.species_rename_var = tk.StringVar()
        self.ent_rename = ttk.Entry(edit_row, textvariable=self.species_rename_var, width=20)
        self.ent_rename.pack(side=tk.LEFT, padx=5)

        btn_rename = ttk.Button(edit_row, text="Update Name", command=self.rename_organism)
        btn_rename.pack(side=tk.LEFT, padx=5)

        grid_frame = ttk.Frame(self.calib_frame)
        grid_frame.pack(fill=tk.X, padx=10, pady=5)

        self.sliders = {}
        slider_configs = [
            ("Lower Hue", "lh", 0, 179),
            ("Upper Hue", "uh", 0, 179),
            ("Lower Saturation", "ls", 0, 255),
            ("Upper Saturation", "us", 0, 255),
            ("Lower Value", "lv", 0, 255),
            ("Upper Value", "uv", 0, 255),
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

    # ==========================================
    # CANVAS INTERACTION & CURVE EDITING
    # ==========================================
    def toggle_edit_zones(self):
        self.edit_sections_mode = not self.edit_sections_mode
        if self.edit_sections_mode:
            self.btn_edit_zones.config(text="EDIT ZONES: ON", bg="#2E7D32")
        else:
            self.btn_edit_zones.config(text="EDIT ZONES: OFF", bg="#E65100")

    def on_canvas_press(self, event):
        x, y = event.x, event.y

        # If Zone Editing mode is active, check if user clicked on a vertex node
        if self.edit_sections_mode:
            for sec_id, pts in self.sections.items():
                for idx, pt in enumerate(pts):
                    dist = np.hypot(x - pt[0], y - pt[1])
                    if dist < 15:  # Handle grab radius
                        self.selected_node = (sec_id, idx)
                        return
            self.selected_node = None
        else:
            # Color sampling mode when Zone Editing is OFF
            if self.current_frame is None:
                return
            h, w, _ = self.current_frame.shape
            if 0 <= x < w and 0 <= y < h:
                x_min, x_max = max(0, x - 2), min(w, x + 3)
                y_min, y_max = max(0, y - 2), min(h, y + 3)
                roi = self.current_frame[y_min:y_max, x_min:x_max]
                roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                avg_hsv = np.mean(roi_hsv, axis=(0, 1)).astype(int)

                h_val, s_val, v_val = avg_hsv[0], avg_hsv[1], avg_hsv[2]

                self.sliders['lh'].set(max(0, h_val - 12))
                self.sliders['uh'].set(min(179, h_val + 12))
                self.sliders['ls'].set(max(30, s_val - 60))
                self.sliders['us'].set(min(255, s_val + 60))
                self.sliders['lv'].set(max(30, v_val - 60))
                self.sliders['uv'].set(min(255, v_val + 60))

                self.on_slider_change(None, None)
                if not self.show_calibrator:
                    self.toggle_calibrator()

    def on_canvas_drag(self, event):
        if self.edit_sections_mode and self.selected_node is not None:
            sec_id, pt_idx = self.selected_node
            # Clamp coordinates to camera frame boundary
            clamped_x = max(0, min(640, event.x))
            clamped_y = max(0, min(480, event.y))
            self.sections[sec_id][pt_idx] = [clamped_x, clamped_y]

    def on_canvas_release(self, event):
        self.selected_node = None

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
        if species not in self.color_ranges:
            return

        spec = self.color_ranges[species]
        lower, upper = spec['lower'], spec['upper']

        self.sliders['lh'].set(lower[0])
        self.sliders['ls'].set(lower[1])
        self.sliders['lv'].set(lower[2])
        self.sliders['uh'].set(upper[0])
        self.sliders['us'].set(upper[1])
        self.sliders['uv'].set(upper[2])

        self.species_enabled_var.set(spec.get('enabled', True))
        self.species_rename_var.set(species)

        self.is_loading_sliders = False
        self.update_color_previews()

    def on_enable_toggle(self):
        species = self.species_var.get()
        if species in self.color_ranges:
            self.color_ranges[species]['enabled'] = self.species_enabled_var.get()

    def rename_organism(self):
        old_name = self.species_var.get()
        new_name = self.species_rename_var.get().strip()

        if not new_name or new_name == old_name:
            return

        if new_name in self.color_ranges:
            messagebox.showerror("Error", f"An organism named '{new_name}' already exists.")
            return

        self.color_ranges[new_name] = self.color_ranges.pop(old_name)
        self.species_combo['values'] = list(self.color_ranges.keys())
        self.species_var.set(new_name)

    def on_slider_change(self, key, value):
        if self.is_loading_sliders:
            return
        species = self.species_var.get()
        if species not in self.color_ranges:
            return

        lh, ls, lv = self.sliders['lh'].get(), self.sliders['ls'].get(), self.sliders['lv'].get()
        uh, us, uv = self.sliders['uh'].get(), self.sliders['us'].get(), self.sliders['uv'].get()

        self.color_ranges[species]['lower'] = np.array([lh, ls, lv])
        self.color_ranges[species]['upper'] = np.array([uh, us, uv])
        self.update_color_previews()

    def update_color_previews(self):
        lh, ls, lv = self.sliders['lh'].get(), self.sliders['ls'].get(), self.sliders['lv'].get()
        uh, us, uv = self.sliders['uh'].get(), self.sliders['us'].get(), self.sliders['uv'].get()

        lower_rgb = cv2.cvtColor(np.uint8([[[lh, ls, lv]]]), cv2.COLOR_HSV2RGB)[0][0]
        upper_rgb = cv2.cvtColor(np.uint8([[[uh, us, uv]]]), cv2.COLOR_HSV2RGB)[0][0]

        self.lbl_lower_rgb.config(text=f"({lower_rgb[0]}, {lower_rgb[1]}, {lower_rgb[2]})")
        self.lbl_upper_rgb.config(text=f"({upper_rgb[0]}, {upper_rgb[1]}, {upper_rgb[2]})")

        self.box_lower.config(bg=f"#{lower_rgb[0]:02x}{lower_rgb[1]:02x}{lower_rgb[2]:02x}")
        self.box_upper.config(bg=f"#{upper_rgb[0]:02x}{upper_rgb[1]:02x}{upper_rgb[2]:02x}")

    def trigger_action(self):
        self.action_triggered = not self.action_triggered
        if self.action_triggered:
            self.btn_action.config(text="ACTION: ON", bg="#2E7D32")
        else:
            self.btn_action.config(text="ACTION: OFF", bg="#D32F2F")

    # ==========================================
    # VIDEO PROCESSING LOOP
    # ==========================================
    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.window.after(30, self.update_frame)
            return

        frame = cv2.resize(frame, (640, 480))
        self.current_frame = frame.copy()

        blurred = cv2.medianBlur(frame, 7)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # 1. DRAW EDITABLE CLOSED CURVES (SECTION POLYGONS)
        for sec_id, pts in self.sections.items():
            pts_np = np.array(pts, dtype=np.int32)
            cv2.polylines(frame, [pts_np], isClosed=True, color=(0, 255, 255), thickness=2)

            # Draw centroid section label
            center_x = int(np.mean([p[0] for p in pts]))
            center_y = int(np.mean([p[1] for p in pts]))
            cv2.putText(frame, f"Sec {sec_id}", (center_x - 20, center_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # If editing zones, draw draggable corner handle points
            if self.edit_sections_mode:
                for pt in pts:
                    cv2.circle(frame, (pt[0], pt[1]), 6, (0, 255, 255), -1)

        detected_organism_id = 0
        detected_section_id = 0
        detected_name = "None"
        global_max_area = 500 

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

        # 2. DETECT SPECIES (ONE PER COLOR CLASS)
        for name, spec in self.color_ranges.items():
            if not spec.get('enabled', True):
                continue

            mask = cv2.inRange(hsv, spec['lower'], spec['upper'])
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)

                if area > 500:  
                    x, y, bw, bh = cv2.boundingRect(largest_contour)
                    cx = float(x + bw // 2)
                    cy = float(y + bh // 2)
                    
                    # Test if object center is inside any custom closed curve
                    section = 0
                    for sec_id, pts in self.sections.items():
                        pts_np = np.array(pts, dtype=np.int32)
                        if cv2.pointPolygonTest(pts_np, (cx, cy), False) >= 0:
                            section = sec_id
                            break

                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), spec['color_bgr'], 2)
                    cv2.putText(frame, f"{name} (Sec {section})", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, spec['color_bgr'], 2)

                    if area > global_max_area:
                        global_max_area = area
                        detected_organism_id = spec['id']
                        detected_section_id = section
                        detected_name = name

        # 3. UPDATE STATUS & SAFE SERIAL WRITE
        if detected_organism_id != 0:
            status_text = f"{detected_name.upper()}\nDETECTED\n\n(SEC {detected_section_id})"
            self.detection_display_label.config(text=status_text, bg="#2E7D32")
        else:
            status_text = "NOT\nDETECTED"
            self.detection_display_label.config(text=status_text, bg="#D32F2F")

        action_flag = 1 if self.action_triggered else 0
        serial_code = f"{detected_organism_id}{detected_section_id}{action_flag}"

        # Safe non-blocking write to Arduino
        if time.time() - self.last_send_time > 0.2:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write((serial_code + '\n').encode('utf-8'))
                except Exception as e:
                    print(f"Serial communication lost: {e}. Switching to offline mode.")
                    self.ser = None
            self.last_send_time = time.time()

        ser_status = "Online" if (self.ser and self.ser.is_open) else "Offline"
        detected_label_status = f"{detected_name} in Sec {detected_section_id}" if detected_organism_id != 0 else "None"
        self.status_label.config(text=f"Detected: {detected_label_status} | Code: {serial_code} | Serial: {ser_status}")

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
            try:
                self.ser.write(b"000\n")
                self.ser.close()
            except Exception:
                pass
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ObjectDetectionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
