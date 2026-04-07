import time
import board
import pwmio
import displayio
import terminalio
import adafruit_vl53l4cd
from digitalio import DigitalInOut, Direction, Pull
from adafruit_display_text import label
from rainbowio import colorwheel
from adafruit_simplemath import map_range, constrain
from adafruit_motor.motor import DCMotor
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
        return self.encoder.position

    @position.setter
    def position(self, position):
        self.encoder.position = position

#------------------------------------------------------------------------------------------------

buttonD0 = Button(board.D0, pull=Pull.UP)
buttonD1 = Button(board.D1, pull=Pull.DOWN)
buttonD2 = Button(board.D2, pull=Pull.DOWN)

pwm1 = pwmio.PWMOut(board.A1, duty_cycle=2 ** 15, frequency=25000)
pwm2 = pwmio.PWMOut(board.A0, duty_cycle=2 ** 15, frequency=25000)
fan = DCMotor(pwm1, pwm2)

i2c = board.I2C()

led_display = Seg7x4(i2c)
led_display.brightness = 0.5

sensor = adafruit_vl53l4cd.VL53L4CD(i2c)
sensor.inter_measurement = 0
sensor.timing_budget = 200

encoderP = Encoder(i2c, 0x36)
encoderI = Encoder(i2c, 0x37)
encoderD = Encoder(i2c, 0x38)

#pixels = [neopixel.NeoPixel(qt_enc1, 6, 1),neopixel.NeoPixel(qt_enc2, 6, 1),neopixel.NeoPixel(qt_enc3, 6, 1)]

display = board.DISPLAY
splash = displayio.Group()
display.root_group = splash

FONTSCALE = 3
BACKGROUND_COLOR = 0x00FF00  # Bright Green
FOREGROUND_COLOR = 0xAA0088  # Purple
TEXT_COLOR = 0x2222FF

text="Ready"
text_area = label.Label(terminalio.FONT, text=text, color=TEXT_COLOR)
text_width = text_area.bounding_box[2] * FONTSCALE
text_group = displayio.Group(
    scale=FONTSCALE,
    x=0,
    y=display.height // 2,
)
text_group.append(text_area)  # Subgroup for text scaling
splash.append(text_group)

cumError = 0
rateError = 0
lastError = 0
timeStep = 0.2

# PIDs to tune
encoderP.position = 10
encoderI.position = 0
encoderD.position = 0

# Lift off value
power=70.

# Setpoint location in mm
setPoint = 10.0

# Encoder increment
enc_step = 0.0002

sensor.start_ranging()

try:
    while True:
        while not sensor.data_ready:
            pass
        sensor.clear_interrupt()

        kP = constrain(encoderP.position * enc_step, 0.0, 1.0)
        kI = constrain(encoderI.position * enc_step, 0.0, 1.0)
        kD = constrain(encoderD.position * enc_step, 0.0, 1.0)

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
        power = constrain(power+new, 0., 100.)
        fan.throttle = power / 100.

        # Update outputs
        print (f"{current:^4.1f}, {error:^4.1f}, {setPoint:^4.1f}, {power:^6.3f}, {kP:.4f}, {kI:.4f}, {kD:.4f}")
        text_area.text = f"E: {error:7.1f}"
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
