import tkinter as tk
from tkinter import ttk
import serial
import threading
import collections
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation

# --- Configuration ---
SERIAL_PORT = '/dev/ttyACM0'  # Change to /dev/ttyACM0 for USB
BAUD_RATE = 9600
MAX_DATA_POINTS = 50

class SerialGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Raspberry Pi Serial Monitor")
        
        # Data storage: deque automatically handles the "scrolling" effect
        self.data_x = collections.deque(range(MAX_DATA_POINTS), maxlen=MAX_DATA_POINTS)
        self.data_y = collections.deque([0.0] * MAX_DATA_POINTS, maxlen=MAX_DATA_POINTS)
        
        # --- UI Layout ---
        self.frame = ttk.Frame(self.root)
        self.frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        self.label = ttk.Label(self.frame, text="Live Serial Stream", font=("Arial", 14))
        self.label.pack()

        # --- Matplotlib Figure ---
        self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=100)
        self.line, = self.ax.plot(self.data_x, self.data_y, color='teal', lw=2)
        self.ax.set_ylim(0, 100) # Adjust based on your expected sensor range
        self.ax.grid(True, linestyle='--', alpha=0.6)

        # Embed Matplotlib into Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # --- Serial Threading ---
        self.running = True
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()

        # --- Animation ---
        # Update the plot every 100ms
        self.ani = FuncAnimation(self.fig, self.update_plot, interval=100, cache_frame_data=False)

    def read_serial(self):
        """Background thread to catch serial data without freezing the UI."""
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                while self.running:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8').rstrip()
                        try:
                            value = float(line.split()[1])
                            self.data_y.append(value)
                        except ValueError:
                            pass
        except Exception as e:
            print(f"Serial error: {e}")

    def update_plot(self, frame):
        """Updates the line data for the animation."""
        self.line.set_ydata(self.data_y)
        return self.line,

    def on_close(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialGuiApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
