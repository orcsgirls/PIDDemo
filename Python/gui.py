import tkinter as tk
from tkinter import ttk
import serial
import threading
import collections
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# --- Configuration ---
SERIAL_PORT = '/dev/ttyACM0'  
BAUD_RATE = 115200
MAX_DATA_POINTS = 1000 # Increased buffer to support longer view windows

class SerialGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pi Serial Monitor (Variable Window)")
        
        # Data storage
        self.data_x = collections.deque(maxlen=MAX_DATA_POINTS)
        self.data_y = collections.deque(maxlen=MAX_DATA_POINTS)
        self.start_time = time.time()
        self.latest_val = 0.0
        self.is_running = True
        
        # --- UI Layout ---
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.val_display = ttk.Label(self.main_frame, text="0.00", font=("Arial", 32, "bold"), foreground="teal")
        self.val_display.pack()

        # Control Buttons Frame
        self.btn_frame = ttk.Frame(self.main_frame)
        self.btn_frame.pack(pady=5)
        
        self.start_btn = ttk.Button(self.btn_frame, text="Start", command=self.start_stream, state="disabled")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(self.btn_frame, text="Stop", command=self.stop_stream)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.quit_btn = ttk.Button(self.btn_frame, text="Quit", command=self.on_close)
        self.quit_btn.pack(side=tk.LEFT, padx=5)

        # --- Slider for Window Length ---
        self.slider_frame = ttk.Frame(self.main_frame)
        self.slider_frame.pack(pady=10, fill=tk.X)
        
        ttk.Label(self.slider_frame, text="View Window (seconds):").pack(side=tk.LEFT, padx=5)
        
        # Slider ranges from 5 to 120 seconds
        self.window_size = tk.IntVar(value=30)
        self.slider = ttk.Scale(self.slider_frame, from_=5, to=120, 
                                variable=self.window_size, orient=tk.HORIZONTAL)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.window_label = ttk.Label(self.slider_frame, text="30s")
        self.window_label.pack(side=tk.LEFT, padx=5)

        # --- Matplotlib Figure ---
        self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=100)
        self.line, = self.ax.plot([], [], color='teal', lw=2)
        self.ax.set_ylim(0, 100)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.ax.grid(True, linestyle='--', alpha=0.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.main_frame)
        self.toolbar.update()

        # --- Serial Threading ---
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()

        self.update_ui()

    def start_stream(self):
        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop_stream(self):
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def read_serial(self):
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                ser.flush()
                while True:
                    if self.is_running and ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            try:
                                parts = line.split(',')
                                if len(parts) >= 2:
                                    value = float(parts[1])
                                    elapsed = time.time() - self.start_time
                                    self.latest_val = value
                                    self.data_x.append(elapsed)
                                    self.data_y.append(value)
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            print(f"Serial error: {e}")

    def update_ui(self):
        # Update Slider Label
        current_win = self.window_size.get()
        self.window_label.config(text=f"{current_win}s")

        if self.is_running and len(self.data_x) > 0:
            self.line.set_data(list(self.data_x), list(self.data_y))
            
            # Use slider value for x-axis range
            current_time = self.data_x[-1]
            self.ax.set_xlim(max(0, current_time - current_win), current_time + (current_win * 0.05))
            
            self.val_display.config(text=f"{self.latest_val:.2f}")
            self.canvas.draw_idle()
        
        self.root.after(100, self.update_ui)

    def on_close(self):
        self.is_running = False
        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialGuiApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
