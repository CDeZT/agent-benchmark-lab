from optics import normalize_profile


def close_list(left, right, eps=1e-9):
    return len(left) == len(right) and all(abs(a - b) < eps for a, b in zip(left, right))


assert close_list(normalize_profile([2.0, 4.0, 6.0]), [0.0, 0.5, 1.0])
assert close_list(normalize_profile([-2.0, 0.0, 2.0]), [0.0, 0.5, 1.0])
assert close_list(normalize_profile([3.0, 3.0, 3.0]), [0.0, 0.0, 0.0])
assert close_list(normalize_profile([]), [])
