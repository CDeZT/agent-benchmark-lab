import math


def gaussian_beam(wavelength_m, waist_radius_m, z_m):
    # Buggy: uses diameter formulas and wrong curvature.
    zr = math.pi * waist_radius_m / wavelength_m
    w = waist_radius_m * (1 + (z_m / zr) ** 2)
    R = z_m + zr ** 2
    return {"rayleigh_m": zr, "w_m": w, "curvature_m": R}
