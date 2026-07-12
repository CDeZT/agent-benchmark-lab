import math


def gaussian_beam(wavelength_m, waist_radius_m, z_m):
    if wavelength_m <= 0 or waist_radius_m <= 0:
        raise ValueError("wavelength and waist must be positive")
    zr = math.pi * waist_radius_m ** 2 / wavelength_m
    w = waist_radius_m * math.sqrt(1.0 + (z_m / zr) ** 2)
    if z_m == 0:
        curvature = math.inf
    else:
        curvature = z_m * (1.0 + (zr / z_m) ** 2)
    return {"rayleigh_m": float(zr), "w_m": float(w), "curvature_m": float(curvature)}
