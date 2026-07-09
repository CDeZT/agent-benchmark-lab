def normalize_profile(samples):
    peak = max(samples)
    return [value / peak for value in samples]
