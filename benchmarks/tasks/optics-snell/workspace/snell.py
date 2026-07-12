import math


def snell_refract(n1, n2, theta1_deg):
    # Buggy: treats degrees as radians and never checks TIR properly.
    theta2 = math.asin((n1 / n2) * math.sin(theta1_deg))
    return theta2


def critical_angle(n1, n2):
    # Buggy: always returns arcsin(n2/n1) in radians without domain checks.
    return math.asin(n2 / n1)
