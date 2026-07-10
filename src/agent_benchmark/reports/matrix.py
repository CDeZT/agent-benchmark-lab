from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_matrix_summary(run_dir: Path, matrix_summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "matrix_summary.json").write_text(
        json.dumps(matrix_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_matrix_markdown(run_dir / "matrix_report.md", matrix_summary)


def _write_matrix_markdown(path: Path, matrix_summary: dict[str, Any]) -> None:
    lines = [
        f"# Matrix Report: {matrix_summary['suite_id']}",
        "",
        f"- Matrix run id: `{matrix_summary['matrix_run_id']}`",
        f"- Combination count: {matrix_summary['combination_count']}",
        "",
        "| Adapter | Model | Budget Profile | Strict Score | Verified Score | Coverage | Mean Duration | Suite Run |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in matrix_summary["combinations"]:
        lines.append(
            f"| `{item['adapter']}` | `{item['model']}` | `{item['budget_profile']}` | "
            f"{item['mean_score']} | {item.get('mean_verified_normalized_score')} | "
            f"{item.get('mean_verified_coverage_percent')}% | {item['mean_duration_seconds']} | "
            f"`{item['suite_run_dir']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
