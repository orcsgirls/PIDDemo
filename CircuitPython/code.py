import time
import math
import board
import pwmio
import displayio
import terminalio
import adafruit_vl53l4cd
from digitalio import DigitalInOut, Direction, Pull
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from rainbowio import colorwheel
from adafruit_simplemath import map_range, constrain
from adafruit_motor.motor import DCMotor, SLOW_DECAY, FAST_DECAY
from adafruit_seesaw import digitalio, rotaryio, seesaw, neopixel
from adafruit_ht16k33.segments import Seg7x4

#------------------------------------------------------------------------------------------------

class Button():
    def __init__(self, pin, pull=Pull.UP):
        self.btn = DigitalInOut(pin)
        self.btn.switch_to_input(pull=pull)
        self.lastState = self.btn.value

    def isPressed(self):
        currentState = self.btn.value
        if currentState != self.lastState:
            self.lastState=currentState
            return currentState
        else:
            return False

    @property
    def value(self):
        return self.btn.value

#------------------------------------------------------------------------------------------------

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

#------------------------------------------------------------------------------------------------

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

#------------------------------------------------------------------------------------------------

class Screen():
    def __init__(self):
        FONTSCALE = 3
        TEXT_COLOR = 0x2222FF
        EXTRA_COLOR = 0xAAAAFF
        BAR_COLOR = 0xFF0000
        BAR_BACKGROUND = 0x2222FF
        BAR_WIDTH = 25
        MARGIN = 5

        self.display = board.DISPLAY
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        self.text_box = displayio.Group(scale=FONTSCALE, x=0, y=0)
        self.text_height = 10
        self.top    = label.Label(terminalio.FONT, color=TEXT_COLOR , text="t", x=MARGIN, y=self.text_height)
        self.middle = label.Label(terminalio.FONT, color=TEXT_COLOR , text="m", x=MARGIN, y=self.text_height * 2)
        self.bottom = label.Label(terminalio.FONT, color=TEXT_COLOR , text="b", x=MARGIN, y=self.text_height * 3)
        self.extra = label.Label(terminalio.FONT, color=EXTRA_COLOR , text="S", x=MARGIN, y=self.text_height * 4)

        self.text_box.append(self.top)
        self.text_box.append(self.middle)
        self.text_box.append(self.bottom)
        self.text_box.append(self.extra)

        self.bar_back_box = displayio.Group(x=self.display.width - BAR_WIDTH - MARGIN, y=0)
        self.bar_back = Rect(x=0, y=MARGIN, width=BAR_WIDTH, height=self.display.height-MARGIN, fill=BAR_BACKGROUND)
        self.bar_back_box.append(self.bar_back)

        self.splash.append(self.text_box)
        self.splash.append(self.bar_back_box)

    def bar(self, error):
        if(math.fabs(error) < 1.5):
            self.bar_back.fill = 0x00cc00
        elif(math.fabs(error) < 3.0):
            self.bar_back.fill = 0xaaaa00
        else:
            self.bar_back.fill = 0xaa0000

#------------------------------------------------------------------------------------------------

buttonD0 = Button(board.D0, pull=Pull.UP)
buttonD1 = Button(board.D1, pull=Pull.DOWN)
buttonD2 = Button(board.D2, pull=Pull.DOWN)

fan = Fan(board.A1, board.A0, frequency=20)

i2c = board.I2C()
led_display = Seg7x4(i2c)
led_display.brightness = 0.4

sensor = adafruit_vl53l4cd.VL53L4CD(i2c)
sensor.inter_measurement = 0
sensor.timing_budget = 200

encoderP = Encoder(i2c, 0x36)
encoderI = Encoder(i2c, 0x37)
encoderD = Encoder(i2c, 0x38)

screen = Screen()

# Some initialisations
cumError = 0
rateError = 0
lastError = 0
timeStep = 0.2

# PIDs to tune
encoderP.position = 10
encoderI.position = 0
encoderD.position = 0

# Lift off value
fan.power = 40.

# Setpoint location in mm
setPoint = 10.0

# Encoder increment
enc_step = 0.0001

sensor.start_ranging()

try:
    while True:
        while not sensor.data_ready:
            pass
        sensor.clear_interrupt()

        kP = encoderP.position * enc_step
        kI = encoderI.position * enc_step
        kD = encoderD.position * enc_step

        current = sensor.distance
        error = current - setPoint
        if(kI > 0):
            cumError += error * timeStep
            cumError = 0 if ((error > 0 and lastError < 0) or (error < 0 and lastError > 0)) else cumError
        else:
            cumError = 0
        rateError = (error - lastError)/timeStep
        lastError = error

        new = kP*error + kI*cumError + kD*rateError
        fan.power = constrain(fan.power+new, 0., 100.)

        # Update outputs
        print (f"{current:^4.1f}, {error:^4.1f}, {setPoint:^4.1f}, {fan.power:^6.3f}, {kP:.4f}, {kI:.4f}, {kD:.4f}")

        # Screen update
        screen.top.text = f"P: {kP:.4f}"
        screen.middle.text = f"I: {kI:.4f}"
        screen.bottom.text = f"D: {kD:.4f}"
        screen.extra.text = f"S:   {setPoint:^5.1f}"
        screen.bar(error)

        #7 Segment disply update
        led_display.print(f"{current: 5.1f}")

        # Buttons
        if buttonD0.isPressed() and setPoint < 25:
            setPoint = setPoint + 5
        if buttonD1.isPressed() and setPoint > 10:
            setPoint = setPoint - 5

        time.sleep(timeStep)

except KeyboardInterrupt:
    sensor.stop_ranging()
    pass
