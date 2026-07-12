def normalize_profile(samples):
    # Buggy baseline: ignores negative baseline shift and flat/empty profiles.
    peak = max(samples)
    return [value / peak for value in samples]
