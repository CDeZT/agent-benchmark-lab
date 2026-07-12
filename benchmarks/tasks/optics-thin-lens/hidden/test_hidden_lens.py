import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))
from lens import thin_lens


def almost(a, b, eps=1e-9):
    return abs(a - b) <= eps


# Diverging lens (f negative): virtual image
v, m = thin_lens(-50.0, 100.0)
assert almost(v, -100.0 / 3.0), v
assert almost(m, 1.0 / 3.0), m

# Object inside focal length of converging lens: virtual erect image
v, m = thin_lens(50.0, 25.0)
assert almost(v, -50.0), v
assert almost(m, 2.0), m

for bad in ((10.0, 0.0), (0.0, 10.0)):
    try:
        thin_lens(*bad)
        raise AssertionError(f"expected ValueError for {bad}")
    except ValueError:
        pass

print("hidden ok")
