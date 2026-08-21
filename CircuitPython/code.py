import time
import math
import board
import pwmio
import displayio
import terminalio
import adafruit_vl53l4cd
from digitalio import DigitalInOut, Pull
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_simplemath import map_range, constrain
from adafruit_motor.motor import DCMotor, FAST_DECAY
from adafruit_seesaw import digitalio, rotaryio, seesaw, neopixel
from adafruit_ht16k33.segments import Seg7x4

# ------------------------------------------------------------------------------------------------

class Button():
    def __init__(self, pin, pull=Pull.UP):
        self.btn = DigitalInOut(pin)
        self.btn.switch_to_input(pull=pull)
        self.lastState = self.btn.value

    def isPressed(self):
        currentState = self.btn.value
        if currentState != self.lastState:
            self.lastState = currentState
            return currentState
        else:
            return False

    @property
    def value(self):
        return self.btn.value

# ------------------------------------------------------------------------------------------------

class Encoder():
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.qt_enc = seesaw.Seesaw(self.i2c, addr=address)
        self.encoder = rotaryio.IncrementalEncoder(self.qt_enc)
        self.pixel = neopixel.NeoPixel(self.qt_enc, 6, 1)
        self.qt_enc.pin_mode(24, self.qt_enc.INPUT_PULLUP)
        self.button = digitalio.DigitalIO(self.qt_enc, 24)

        self.pixel.brightness = 0.2
        self.pixel.fill(0x00ff00)

    @property
    def position(self):
        if self.encoder.position < 0:
            self.encoder.position = 0
        return self.encoder.position

    @position.setter
    def position(self, position):
        self.encoder.position = position

    @property
    def color(self):
        return None

    @color.setter
    def color(self, value):
        self.pixel.fill(value)

# ------------------------------------------------------------------------------------------------

class Fan():
    def __init__(self, pinA, pinB, frequency=20):
        pwm1 = pwmio.PWMOut(pinA, duty_cycle=2 ** 15, frequency=frequency)
        pwm2 = pwmio.PWMOut(pinB, duty_cycle=2 ** 15, frequency=frequency)
        self.fan = DCMotor(pwm1, pwm2)
        self.fan.decay_mode = FAST_DECAY

    @property
    def power(self):
        return self.fan.throttle * 100.

    @power.setter
    def power(self, power):
        self.fan.throttle = power / 100.

# ------------------------------------------------------------------------------------------------

class Screen():
    def __init__(self):
        FONTSCALE = 3
        TEXT_COLOR = 0x2222FF
        EXTRA_COLOR = 0xAAAAFF
        BAR_BACKGROUND = 0x2222FF
        BAR_WIDTH = 25
        MARGIN = 5

        self.display = board.DISPLAY
        self.display.auto_refresh = False
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        self.text_box = displayio.Group(scale=FONTSCALE, x=0, y=0)
        self.text_height = 10
        self.top    = label.Label(terminalio.FONT, color=TEXT_COLOR, text="t", x=MARGIN, y=self.text_height)
        self.middle = label.Label(terminalio.FONT, color=TEXT_COLOR, text="m", x=MARGIN, y=self.text_height * 2)
        self.bottom = label.Label(terminalio.FONT, color=TEXT_COLOR, text="b", x=MARGIN, y=self.text_height * 3)
        self.extra  = label.Label(terminalio.FONT, color=EXTRA_COLOR, text="S", x=MARGIN, y=self.text_height * 4)

        self.text_box.append(self.top)
        self.text_box.append(self.middle)
        self.text_box.append(self.bottom)
        self.text_box.append(self.extra)

        self.bar_back_box = displayio.Group(x=self.display.width - BAR_WIDTH - MARGIN, y=0)
        self.bar_back = Rect(x=0, y=MARGIN, width=BAR_WIDTH, height=self.display.height - MARGIN, fill=BAR_BACKGROUND)
        self.bar_back_box.append(self.bar_back)

        self.splash.append(self.text_box)
        self.splash.append(self.bar_back_box)

        # ---- Graph surface (mode 2) --------------------------------------
        GRAPH_BG       = 0x000022
        GRAPH_TRACE    = 0x00ff00
        GRAPH_SETPOINT = 0xffaa00

        self.graph_x = MARGIN
        self.graph_y = MARGIN
        self.graph_width  = self.display.width - BAR_WIDTH - 4 * MARGIN
        self.graph_height = self.display.height - 2 * MARGIN

        self.graph_palette = displayio.Palette(3)
        self.graph_palette[0] = GRAPH_BG        # background
        self.graph_palette[1] = GRAPH_TRACE     # height trace
        self.graph_palette[2] = GRAPH_SETPOINT  # setpoint line

        self.graph_bitmap = displayio.Bitmap(self.graph_width, self.graph_height, 3)
        self.graph_tile = displayio.TileGrid(
            self.graph_bitmap, pixel_shader=self.graph_palette,
            x=self.graph_x, y=self.graph_y)
        self.graph_box = displayio.Group()
        self.graph_box.append(self.graph_tile)
        self.splash.append(self.graph_box)
        self.graph_box.hidden = True

        # Range mapped onto the graph height, and the rolling sample buffer
        self.graph_min  = 1.0
        self.graph_max  = 33.0
        self.max_points = self.graph_width
        self.history    = []

    def refresh(self):
        self.display.refresh()

    def bar(self, error):
        if math.fabs(error) < 1.5:
            self.bar_back.fill = 0x00cc00
        elif math.fabs(error) < 3.0:
            self.bar_back.fill = 0xaaaa00
        else:
            self.bar_back.fill = 0xaa0000

    def show_text(self):
        self.text_box.hidden = False
        self.graph_box.hidden = True

    def show_graph(self):
        self.text_box.hidden = True
        self.graph_box.hidden = False

    def _to_y(self, value):
        y = map_range(value, self.graph_min, self.graph_max,
                      self.graph_height - 1, 0)
        return int(constrain(y, 0, self.graph_height - 1))

    def graph(self, current, setPoint):
        self.history.append(current)
        if len(self.history) > self.max_points:
            self.history.pop(0)

        self.graph_bitmap.fill(0)

        # Setpoint line (index 2), full width
        sp_y = self._to_y(setPoint)
        for x in range(self.graph_width):
            self.graph_bitmap[x, sp_y] = 2

        # Height trace (index 1)
        n = len(self.history)
        prev_y = None
        for i in range(n):
            x = self.graph_width - n + i
            if x < 0:
                prev_y = None
                continue
            y = self._to_y(self.history[i])
            if prev_y is None:
                self.graph_bitmap[x, y] = 1
            else:
                for yy in range(min(prev_y, y), max(prev_y, y) + 1):
                    self.graph_bitmap[x, yy] = 1
            prev_y = y

# ------------------------------------------------------------------------------------------------

buttonD0 = Button(board.D0, pull=Pull.UP)
buttonD1 = Button(board.D1, pull=Pull.DOWN)
buttonD2 = Button(board.D2, pull=Pull.DOWN)

fan = Fan(board.A1, board.A0, frequency=20)

i2c = board.I2C()
led_display = Seg7x4(i2c)
led_display.brightness = 0.4

sensor = adafruit_vl53l4cd.VL53L4CD(i2c)
sensor.inter_measurement = 0
sensor.timing_budget = 50   # 50 ms (or 33 ms if supported)

encoderP = Encoder(i2c, 0x36)
encoderI = Encoder(i2c, 0x37)
encoderD = Encoder(i2c, 0x38)

screen = Screen()

# --- Initial State & Loop Timing ---
timeStep = 0.05             # 50 ms (20 Hz loop rate)
setPoint = 10.0
screen_mode = 0

enc_step_P = 0.01
enc_step_I = 0.005
enc_step_D = 0.005

# Encoder initial positions
encoderP.position = 0
encoderI.position = 0
encoderD.position = 0

# --- Configuration Constants ---
HOVER_BIAS    = 35.0   # % power needed to roughly float the ball in the middle
MIN_FAN_POWER = 17.0   # Minimum floor to prevent motor stall
MAX_FAN_POWER = 100.0
MAX_INTEGRAL  = 20.0
ALPHA_FILTER  = 0.5    # Higher alpha = less phase delay

# Persistent PID & Filter States
cumError = 0.0
filtered_distance = None
last_distance = None

sensor.start_ranging()
lastRun = time.monotonic()

try:
    while True:
        # --- Poll buttons every pass so they feel responsive -------------
        if buttonD0.isPressed() and setPoint <= 24:
            setPoint += 2
        if buttonD1.isPressed() and setPoint >= 8:
            setPoint -= 2
        if buttonD2.isPressed():
            screen_mode = (screen_mode + 1) % 3

        # --- Heavy work (sensor, PID, display) only every timeStep -------
        now = time.monotonic()
        dt = now - lastRun
        if sensor.data_ready and dt >= timeStep:
            lastRun = now
            sensor.clear_interrupt()

            kP = encoderP.position * enc_step_P
            kI = encoderI.position * enc_step_I
            kD = encoderD.position * enc_step_D

            encoderP.color = 0xff0000 if kP == 0 else 0x00ff00
            encoderI.color = 0xff0000 if kI == 0 else 0x00ff00
            encoderD.color = 0xff0000 if kD == 0 else 0x00ff00

            raw_current = sensor.distance

            # --- Sensor Low-Pass Filter (Dampening) ---
            if filtered_distance is None:
                filtered_distance = raw_current
                last_distance = raw_current
            else:
                filtered_distance = (ALPHA_FILTER * raw_current) + ((1.0 - ALPHA_FILTER) * filtered_distance)

            current = filtered_distance

            # --- 1. Error Calculation ---
            error = current - setPoint

            # --- 2. Derivative on Measurement (Prevents Setpoint Kick) ---
            d_measurement = (current - last_distance) / dt if dt > 0 else 0.0
            last_distance = current

            # Push harder when too low to catch drops; reduce gently when too high
            if error > 0:  # Ball too low
                p_term = kP * 1.4 * error
            else:          # Ball too high
                p_term = kP * 0.6 * error

            d_term = kD * d_measurement

            # Anti-windup clamped integral
            if kI > 0:
                cumError += error * dt
                max_i_accum = MAX_INTEGRAL / kI
                cumError = constrain(cumError, -max_i_accum, max_i_accum)
                i_term = kI * cumError
            else:
                cumError = 0.0
                i_term = 0.0

            # --- 4. Control Effort & Clamping ---
            pid_correction = p_term + i_term + d_term
            target_power = HOVER_BIAS + pid_correction
            fan.power = constrain(target_power, MIN_FAN_POWER, MAX_FAN_POWER)

            print(f"{current:^4.1f}, {error:^4.1f}, {setPoint:^4.1f}, {fan.power:^6.3f}, {kP:.4f}, {kI:.4f}, {kD:.4f}")

            # --- Screen update ---
            if screen_mode == 0:
                screen.show_text()
                screen.top.text = f"P: {kP:.4f}"
                screen.middle.text = f"I: {kI:.4f}"
                screen.bottom.text = f"D: {kD:.4f}"
                screen.extra.text = f"S:   {setPoint:^5.1f}"
                screen.bar(error)
            elif screen_mode == 1:
                screen.show_text()
                screen.top.text = f"He: {current:6.2f}"
                screen.middle.text = f"Fa: {fan.power:6.2f}"
                screen.bottom.text = f"Er: {error:6.2f}"
                screen.extra.text = f"SP: {setPoint:6.2f}"
                screen.bar(error)
            elif screen_mode == 2:
                screen.show_graph()
                screen.graph(current, setPoint)
                screen.bar(error)

            # 7-segment display + frame refresh
            led_display.print(f"{current: 5.1f}")
            screen.refresh()

        time.sleep(0.005)

except KeyboardInterrupt:
    fan.power = 0.0
    sensor.stop_ranging()
