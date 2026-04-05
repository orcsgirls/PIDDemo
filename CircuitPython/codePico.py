import time
import board
import busio
import digitalio
import analogio
import pwmio
import adafruit_vl53l0x
from adafruit_simplemath import map_range, constrain
from adafruit_motor.motor import DCMotor
from adafruit_seesaw import digitalio, rotaryio, seesaw, neopixel

pwm1 = pwmio.PWMOut(board.GP14, duty_cycle=2 ** 15, frequency=25000)
pwm2 = pwmio.PWMOut(board.GP15, duty_cycle=2 ** 15, frequency=25000)
fan = DCMotor(pwm1, pwm2)

i2c = busio.I2C(board.GP17, board.GP16)
sensor = adafruit_vl53l0x.VL53L0X(i2c)
sensor.measurement_timing_budget = 33000 # 33ms is the default - longer more accurate but slower

qt_enc1 = seesaw.Seesaw(i2c, addr=0x36)
qt_enc2 = seesaw.Seesaw(i2c, addr=0x37)
qt_enc3 = seesaw.Seesaw(i2c, addr=0x38)

encoder1 = rotaryio.IncrementalEncoder(qt_enc1)
encoder2 = rotaryio.IncrementalEncoder(qt_enc2)
encoder3 = rotaryio.IncrementalEncoder(qt_enc3)

last_position1 = None
last_position2 = None
last_position3 = None

cumError = 0
rateError = 0
lastError = 0
timeStep = 0.2

# PIDs to tune
kP = 0.001
kI = 0.000
kD = 0.000

# Lift off value
power=70.

# Setpoint location in mm
setPoint = 100

# Encoder increment
enc_step = 0.001

with sensor.continuous_mode():
    while True:
        kP = -encoder1.position * enc_step
        kD = -encoder2.position * enc_step
        kI = -encoder3.position * enc_step

        current = sensor.range
        error = current - setPoint
        cumError += error * timeStep
        cumError = 0 if ((error > 0 and lastError < 0) or (error < 0 and lastError > 0)) else cumError
        rateError = (error - lastError)/timeStep
        lastError = error

        new = kP*error + kI*cumError + kD*rateError
        power = constrain(power+new, 0., 100.)
        fan.throttle = power / 100.

        pwm.duty_cycle=int(power)
        print (f"({current:^4.1f}, {error:^4}, {new:^5.3f}, {power:^6.3f}, {kP:.4f}, {kD:.4f}, {kI:.4f})")

        time.sleep(timeStep)
