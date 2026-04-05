import time
import board
import digitalio
import pwmio
import displayio
import terminalio
import adafruit_vl53l0x
from adafruit_display_text import label
from rainbowio import colorwheel
from adafruit_simplemath import map_range, constrain
from adafruit_motor.motor import DCMotor
from adafruit_seesaw import digitalio, rotaryio, seesaw, neopixel

pwm1 = pwmio.PWMOut(board.A1, duty_cycle=2 ** 15, frequency=25000)
pwm2 = pwmio.PWMOut(board.A0, duty_cycle=2 ** 15, frequency=25000)
fan = DCMotor(pwm1, pwm2)

i2c = board.I2C()

qt_enc1 = seesaw.Seesaw(i2c, addr=0x36)
qt_enc2 = seesaw.Seesaw(i2c, addr=0x37)
qt_enc3 = seesaw.Seesaw(i2c, addr=0x38)

pixels = [neopixel.NeoPixel(qt_enc1, 6, 1),neopixel.NeoPixel(qt_enc2, 6, 1),neopixel.NeoPixel(qt_enc3, 6, 1)]

display = board.DISPLAY
splash = displayio.Group()
display.root_group = splash

FONTSCALE = 3
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
    p.fill(0xff0000)

encoder1 = rotaryio.IncrementalEncoder(qt_enc1)
encoder2 = rotaryio.IncrementalEncoder(qt_enc2)
encoder3 = rotaryio.IncrementalEncoder(qt_enc3)

last_position1 = None
last_position2 = None
last_position3 = None

increment = 0.2
power = 0.0
encoder1.position = int(70 / increment)

while True:
    power = encoder1.position * increment
    text_area.text = f"P: {power:5.1f}%"

    fan.throttle = min(power / 100., 1.0)

    print(f"Demo, {power}")

    time.sleep(0.2)

