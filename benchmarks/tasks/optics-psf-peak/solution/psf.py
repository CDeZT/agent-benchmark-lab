def measure_psf(samples):
    if not samples:
        return (0.0, 0.0)
    peak = max(samples)
    if peak <= 0:
        return (float(peak), 0.0)
    half = peak / 2.0
    peak_i = max(range(len(samples)), key=lambda i: samples[i])

    def cross(i0, i1):
        y0, y1 = samples[i0], samples[i1]
        if y0 == y1:
            return float(i0)
        return i0 + (half - y0) / (y1 - y0)

    left = None
    for i in range(peak_i, 0, -1):
        if samples[i] >= half and samples[i - 1] < half:
            left = cross(i - 1, i)
            break
        if samples[i] < half:
            break
    right = None
    for i in range(peak_i, len(samples) - 1):
        if samples[i] >= half and samples[i + 1] < half:
            right = cross(i, i + 1)
            break
        if samples[i] < half:
            break
    if left is None or right is None:
        return (float(peak), 0.0)
    return (float(peak), float(right - left))
