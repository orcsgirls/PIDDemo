import time
import board
import digitalio
import pwmio
import displayio
import terminalio
import adafruit_vl53l4cd
from adafruit_display_text import label
from rainbowio import colorwheel
from adafruit_simplemath import map_range, constrain
from adafruit_motor.motor import DCMotor
from adafruit_seesaw import digitalio, rotaryio, seesaw, neopixel

pwm1 = pwmio.PWMOut(board.A1, duty_cycle=2 ** 15, frequency=25000)
pwm2 = pwmio.PWMOut(board.A0, duty_cycle=2 ** 15, frequency=25000)
fan = DCMotor(pwm1, pwm2)

i2c = board.I2C()

sensor = adafruit_vl53l4cd.VL53L4CD(i2c)
sensor.measurement_timing_budget = 33000 # 33ms is the default - longer more accurate but slower

qt_enc1 = seesaw.Seesaw(i2c, addr=0x36)
qt_enc2 = seesaw.Seesaw(i2c, addr=0x37)
qt_enc3 = seesaw.Seesaw(i2c, addr=0x38)

pixels = [neopixel.NeoPixel(qt_enc1, 6, 1),neopixel.NeoPixel(qt_enc2, 6, 1),neopixel.NeoPixel(qt_enc3, 6, 1)]

display = board.DISPLAY
splash = displayio.Group()
display.root_group = splash

FONTSCALE = 2
BACKGROUND_COLOR = 0x00FF00  # Bright Green
FOREGROUND_COLOR = 0xAA0088  # Purple
TEXT_COLOR = 0xFFFF00

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

for p in pixels:
    p.brightness = 0.2
    p.fill(0x00ff00)

encoderP = rotaryio.IncrementalEncoder(qt_enc1)
encoderI = rotaryio.IncrementalEncoder(qt_enc2)
encoderD = rotaryio.IncrementalEncoder(qt_enc3)

cumError = 0
rateError = 0
lastError = 0
timeStep = 0.1

# PIDs to tune
encoderP.position = 1
encoderI.position = 0
encoderD.position = 0

# Lift off value
power=70.

# Setpoint location in mm
setPoint = 10.0

# Encoder increment
enc_step = 0.001

sensor.start_ranging()

while True:
    while not sensor.data_ready:
        pass
    sensor.clear_interrupt()

    kP = constrain(encoderP.position * enc_step, 0.0, 1.0)
    kI = constrain(encoderI.position * enc_step, 0.0, 1.0)
    kD = constrain(encoderD.position * enc_step, 0.0, 1.0)

    current = sensor.distance
    error = current - setPoint
    cumError += error * timeStep
    cumError = 0 if ((error > 0 and lastError < 0) or (error < 0 and lastError > 0)) else cumError
    rateError = (error - lastError)/timeStep
    lastError = error

    new = kP*error + kI*cumError + kD*rateError
    power = constrain(power+new, 0., 100.)
    fan.throttle = power / 100.

    print (f"{current:^4.2f}, {error:^4.2f}, {new:^5.3f}, {power:^6.3f}, {kP:.4f}, {kI:.4f}, {kD:.4f}")

    text_area.text = f"E: {error:7.2f}"
    time.sleep(timeStep)
