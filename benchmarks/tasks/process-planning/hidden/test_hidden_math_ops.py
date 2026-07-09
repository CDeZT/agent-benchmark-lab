import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

from math_ops import double


assert double(-3) == -6
assert double(7) == 14
