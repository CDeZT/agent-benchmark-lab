from lens import thin_lens


def almost(a, b, eps=1e-9):
    return abs(a - b) <= eps


v, m = thin_lens(50.0, 100.0)
assert almost(v, 100.0), v
assert almost(m, -1.0), m

v, m = thin_lens(100.0, 200.0)
assert almost(v, 200.0), v
assert almost(m, -1.0), m

try:
    thin_lens(0.0, 100.0)
    raise AssertionError("expected ValueError for f=0")
except ValueError:
    pass

print("ok")
