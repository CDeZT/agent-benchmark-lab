import math


def young_fringe_spacing(wavelength_m, slit_separation_m, screen_distance_m):
    if wavelength_m <= 0 or slit_separation_m <= 0 or screen_distance_m <= 0:
        raise ValueError("wavelength, slit separation, and screen distance must be positive")
    return wavelength_m * screen_distance_m / slit_separation_m


def path_difference(slit_separation_m, angle_rad):
    if slit_separation_m <= 0:
        raise ValueError("slit separation must be positive")
    return slit_separation_m * math.sin(angle_rad)
