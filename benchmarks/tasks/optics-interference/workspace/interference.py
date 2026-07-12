import math


def young_fringe_spacing(wavelength_m, slit_separation_m, screen_distance_m):
    # Buggy: inverted formula
    return slit_separation_m * screen_distance_m / wavelength_m


def path_difference(slit_separation_m, angle_rad):
    # Buggy: uses cos instead of sin
    return slit_separation_m * math.cos(angle_rad)
