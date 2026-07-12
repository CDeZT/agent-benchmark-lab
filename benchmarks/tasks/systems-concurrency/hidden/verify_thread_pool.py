"""Private structural checks for the thread-pool concurrency contract."""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys


workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
source = (workspace / "thread_pool.c").read_text(encoding="utf-8")


def require(pattern: str, message: str) -> None:
    if not re.search(pattern, source, flags=re.MULTILINE):
        raise AssertionError(message)


require(r"pthread_mutex_t\s+mutex\s*;", "thread pool needs a queue mutex")
require(r"pthread_cond_t\s+cond\s*;", "thread pool needs a condition variable")
require(r"pthread_mutex_lock\s*\(\s*&p->mutex\s*\)", "queue operations must acquire the mutex")
require(r"pthread_cond_wait\s*\(", "workers or submitters must wait on a condition variable")
require(r"pthread_cond_(signal|broadcast)\s*\(", "queue state changes must wake waiters")
if re.search(r"while\s*\(\s*!p->shutdown\s*\|\|\s*p->count\s*>\s*0\s*\)", source):
    raise AssertionError("busy-wait worker loop is still present")

print("hidden concurrency structure checks passed")
