from __future__ import annotations

import math
import statistics
from typing import Sequence


# Two-sided 95% Student-t critical values for the small samples the benchmark
# normally uses. Larger samples use the conventional normal approximation.
_T95_BY_DF = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
}


def confidence_interval_95(values: Sequence[float]) -> dict[str, float | int | str] | None:
    """Return a two-sided 95% CI for a repeated measurement mean.

    One observation cannot estimate repeatability, so callers receive ``None``
    rather than a deceptive zero-width interval. The interval uses sample
    standard deviation and Student-t critical values for 2-30 observations.
    """
    sample = [float(value) for value in values]
    count = len(sample)
    if count < 2:
        return None
    mean = statistics.mean(sample)
    standard_error = statistics.stdev(sample) / math.sqrt(count)
    critical = _T95_BY_DF.get(count - 1, 1.96)
    margin = critical * standard_error
    return {
        "confidence_level": 0.95,
        "n": count,
        "method": "two_sided_student_t" if count <= 30 else "two_sided_normal_approximation",
        "lower": round(mean - margin, 4),
        "upper": round(mean + margin, 4),
        "margin": round(margin, 4),
    }
