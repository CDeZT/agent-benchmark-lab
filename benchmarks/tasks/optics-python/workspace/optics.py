def normalize_profile(samples):
    # Buggy baseline: ignores negative baseline shift and zero dynamic range.
    peak = max(samples)
    return [value / peak for value in samples]
