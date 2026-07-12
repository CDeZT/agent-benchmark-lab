def thin_lens(f, u):
    """Return (image_distance v, lateral_magnification m)."""
    if f == 0 or u == 0:
        raise ValueError("f and u must be non-zero")
    inv_v = 1.0 / f - 1.0 / u
    if inv_v == 0:
        raise ValueError("image at infinity")
    v = 1.0 / inv_v
    m = -v / u
    return (float(v), float(m))
