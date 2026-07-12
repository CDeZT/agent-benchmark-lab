import math


def snell_refract(n1, n2, theta1_deg):
    if n1 <= 0 or n2 <= 0:
        raise ValueError("indices must be positive")
    if theta1_deg < 0 or theta1_deg > 90:
        raise ValueError("incidence angle must be in [0, 90] degrees")
    arg = (n1 / n2) * math.sin(math.radians(theta1_deg))
    if arg > 1.0 + 1e-12:
        return None
    if arg > 1.0:
        arg = 1.0
    return math.degrees(math.asin(arg))


def critical_angle(n1, n2):
    if n1 <= 0 or n2 <= 0:
        raise ValueError("indices must be positive")
    if n1 <= n2:
        return None
    return math.degrees(math.asin(n2 / n1))
