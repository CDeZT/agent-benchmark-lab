def thin_lens(f, u):
    """Return (image_distance v, lateral_magnification m)."""
    # Buggy baseline: wrong magnification sign and no zero checks.
    v = 1.0 / (1.0 / f - 1.0 / u)
    m = v / u
    return (v, m)
