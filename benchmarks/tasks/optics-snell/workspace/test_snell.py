from snell import snell_refract, critical_angle
import math


def almost(a, b, eps=1e-6):
    return abs(a - b) <= eps


# Air to glass ~ n=1.5 at 30 deg
t = snell_refract(1.0, 1.5, 30.0)
assert almost(t, math.degrees(math.asin((1.0 / 1.5) * math.sin(math.radians(30.0))))), t

# Glass to air at high angle -> TIR
assert snell_refract(1.5, 1.0, 50.0) is None

c = critical_angle(1.5, 1.0)
assert almost(c, math.degrees(math.asin(1.0 / 1.5))), c
assert critical_angle(1.0, 1.5) is None

print("ok")
