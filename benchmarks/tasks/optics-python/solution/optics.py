def normalize_profile(samples):
    if not samples:
        return []
    baseline = min(samples)
    shifted = [value - baseline for value in samples]
    peak = max(shifted)
    if peak <= 0:
        return [0.0 for _ in samples]
    return [value / peak for value in shifted]
