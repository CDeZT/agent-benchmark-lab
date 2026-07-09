from pathlib import Path
import os

html = Path(os.environ["AGENT_BENCH_WORKSPACE"], "index.html").read_text(encoding="utf-8")

assert "<h1>System Status</h1>" in html
assert 'id="status">PASS<' in html
assert "<script" not in html.lower()
assert "TODO" not in html
