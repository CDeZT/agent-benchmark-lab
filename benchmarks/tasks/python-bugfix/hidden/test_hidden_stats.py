import sys
from pathlib import Path

workspace = Path(__import__("os").environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

from stats import average


assert average([1, 2]) == 1.5
assert average([-2, 2]) == 0.0
assert average(()) == 0.0
