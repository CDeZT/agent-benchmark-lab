from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_benchmark.reports.html import _radar_svg


def write_suite_summary(run_dir: Path, suite_summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "suite_summary.json").write_text(
        json.dumps(suite_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_suite_markdown(run_dir / "suite_report.md", suite_summary)
    _write_suite_html(run_dir / "suite_report.html", suite_summary)


def _write_suite_markdown(path: Path, suite_summary: dict[str, Any]) -> None:
    lines = [
        f"# Suite Report: {suite_summary['suite_id']}",
        "",
        f"- Adapter: `{suite_summary['adapter']}`",
        f"- Model: `{suite_summary['model']}`",
        f"- Adapter model: `{suite_summary.get('adapter_model', suite_summary['model'])}`",
        f"- Budget profile: `{suite_summary['budget_profile']}`",
        f"- Repetitions per task: {suite_summary['repetitions_per_task']}",
        f"- Task count: {suite_summary['task_count']}",
        f"- Mean score: {suite_summary['mean_score']}",
        f"- Mean verified normalized score: {suite_summary.get('mean_verified_normalized_score')}",
        f"- Mean verified evidence coverage: {suite_summary.get('mean_verified_coverage_percent')}%",
        f"- Mean duration seconds: {suite_summary['mean_duration_seconds']}",
    ]
    official_track = suite_summary.get("official_tracks")
    decision_index = suite_summary.get("decision_index")
    if isinstance(decision_index, dict):
        components = decision_index.get("components") if isinstance(decision_index.get("components"), dict) else {}
        lines.extend(
            [
                "## Decision Index",
                "",
                f"- Profile: `{decision_index.get('profile_id')}` ({decision_index.get('profile_fingerprint')})",
                f"- Status: **{decision_index.get('status')}**",
                f"- Score: **{decision_index.get('score')}**",
                f"- Local verified-normalized component: {components.get('local_verified_normalized_score')} (coverage {components.get('local_verified_coverage_percent')}%)",
                f"- Official SWE resolution component: {components.get('official_swe_resolution_rate_percent')}% ({components.get('official_scorable_attempt_count')} scorable attempts)",
                f"- Warnings: {', '.join(str(item) for item in decision_index.get('warnings', [])) or 'none'}",
                f"- Policy: {decision_index.get('policy')}",
                "",
            ]
        )
    if isinstance(official_track, dict) and official_track.get("task_count"):
        lines.extend(
            [
                "## Official Resolution Track",
                "",
                f"- Ranking candidates: {official_track.get('ranking_candidate_task_count')}",
                f"- Scorable official attempts: {official_track.get('scorable_attempt_count')}",
                f"- Resolved official attempts: {official_track.get('resolved_attempt_count')}",
                f"- Official resolution rate: {official_track.get('resolution_rate_percent')}%",
                f"- Policy: {official_track.get('policy')}",
                "",
                "| Official task | Role | Difficulty | Resolved / scorable attempts | Rate | Variance | 95% CI | Evaluator classification | Evidence |",
                "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
            ]
        )
        for task in official_track.get("task_outcomes", []):
            if not isinstance(task, dict):
                continue
            lines.append(
                f"| `{task.get('task_id')}` | {task.get('role')} | {task.get('difficulty')} | "
                f"{task.get('resolved_attempt_count')} / {task.get('scorable_attempt_count')} / {task.get('attempt_count')} | "
                f"{task.get('resolution_rate_percent')}% | {task.get('variance')} | "
                f"{_format_interval(task.get('score_confidence_interval_95'))} | {task.get('classification')} | "
                f"`{task.get('experiment_dir')}` |"
        )
        lines.append("")
    lines.extend(
        [
            "## Local Task Results",
            "",
            "| Task | Strict Score | Score 95% CI | Verified Score | Coverage | Mean Duration | Variance | Experiment |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for task in suite_summary["tasks"]:
        if _is_official_task(task):
            continue
        lines.append(
            f"| `{task['task_id']}` | {task['mean_score']} | {_format_interval(task.get('score_confidence_interval_95'))} | {task.get('mean_verified_normalized_score')} | "
            f"{task.get('mean_verified_coverage_percent')}% | {task['mean_duration_seconds']} | "
            f"{task['variance']} | `{task['experiment_dir']}` |"
        )
    scorecard = suite_summary.get("evaluation_axis_scorecard", {})
    axes = scorecard.get("axes", {}) if isinstance(scorecard, dict) else {}
    if axes:
        lines.extend(["", "## Outcome Capability Scorecard", "", "| Axis | Tasks | Strict | Verified | Coverage |", "| --- | ---: | ---: | ---: | ---: |"])
        for axis, values in axes.items():
            lines.append(
                f"| {values['title']} (`{axis}`) | {values['task_count']} | {values['mean_strict_score']} | "
                f"{values['mean_verified_normalized_score']} | {values['mean_verified_coverage_percent']}% |"
            )
        domain_total = scorecard.get("domain_weighted_total") if isinstance(scorecard, dict) else None
        if isinstance(domain_total, dict) and domain_total.get("usable"):
            lines.extend(
                [
                    "",
                    "## Domain-Weighted Total",
                    "",
                    f"- Strict domain total: **{domain_total.get('strict')}**",
                    f"- Verified-normalized domain total: **{domain_total.get('verified_normalized')}**",
                    f"- Active weight sum: {domain_total.get('active_weight_sum')} (missing axes renormalized out: "
                    f"{', '.join(f'`{a}`' for a in domain_total.get('missing_axes') or []) or 'none'})",
                    f"- Policy: {domain_total.get('policy')}",
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_suite_html(path: Path, suite_summary: dict[str, Any]) -> None:
    """Suite HTML with domain-axis radar (optics/C/embedded axes), not only 10 process dims."""
    scorecard = suite_summary.get("evaluation_axis_scorecard", {})
    axes = scorecard.get("axes", {}) if isinstance(scorecard, dict) else {}
    domain_values: dict[str, float] = {}
    for axis, values in axes.items():
        if isinstance(values, dict) and values.get("mean_strict_score") is not None:
            title = str(values.get("title") or axis)
            domain_values[title] = float(values["mean_strict_score"])
    domain_radar = _radar_svg(domain_values) if domain_values else "<p class='muted'>No domain axes yet (suite may lack optics/C/embedded tags).</p>"

    # Also show mean of per-task 10-dimension radars when available.
    dim_means: dict[str, list[float]] = {}
    for task in suite_summary.get("tasks", []):
        if _is_official_task(task):
            continue
        dims = task.get("mean_dimensions") or task.get("dimensions")
        if not isinstance(dims, dict):
            # Fall back to averaging dimensions from embedded run records.
            runs = task.get("runs") if isinstance(task.get("runs"), list) else []
            per_dim: dict[str, list[float]] = {}
            for run in runs:
                if not isinstance(run, dict):
                    continue
                run_dims = run.get("dimensions")
                if not isinstance(run_dims, dict):
                    continue
                for key, value in run_dims.items():
                    if isinstance(value, (int, float)):
                        per_dim.setdefault(str(key), []).append(float(value))
            dims = {
                key: sum(vals) / len(vals) for key, vals in per_dim.items() if vals
            }
        if isinstance(dims, dict):
            for key, value in dims.items():
                if isinstance(value, (int, float)):
                    dim_means.setdefault(str(key), []).append(float(value))
    process_values = {
        key: round(sum(vals) / len(vals), 2) for key, vals in dim_means.items() if vals
    }
    process_radar = _radar_svg(process_values) if process_values else "<p class='muted'>No process-dimension averages available on this suite summary.</p>"

    domain_total = scorecard.get("domain_weighted_total") if isinstance(scorecard, dict) else None
    domain_total_html = ""
    if isinstance(domain_total, dict) and domain_total.get("usable"):
        domain_total_html = (
            f"<p><b>Domain-weighted strict total:</b> {domain_total.get('strict')} "
            f"(missing axes renormalized: {', '.join(domain_total.get('missing_axes') or []) or 'none'})</p>"
        )

    official_track = suite_summary.get("official_tracks")
    decision_index = suite_summary.get("decision_index")
    decision_index_html = ""
    if isinstance(decision_index, dict):
        components = decision_index.get("components") if isinstance(decision_index.get("components"), dict) else {}
        decision_index_html = (
            "<section><h2>Decision Index</h2>"
            "<p class='muted'>A versioned personal selection aid. It does not replace either native score track.</p>"
            f"<p>Profile: <code>{decision_index.get('profile_id')}</code>; status: <b>{decision_index.get('status')}</b>; "
            f"score: <b>{decision_index.get('score')}</b>.</p>"
            f"<p>Local verified-normalized: {components.get('local_verified_normalized_score')} "
            f"(coverage {components.get('local_verified_coverage_percent')}%); official SWE resolution: "
            f"{components.get('official_swe_resolution_rate_percent')}%.</p>"
            f"<p class='muted'>Warnings: {', '.join(str(item) for item in decision_index.get('warnings', [])) or 'none'}.</p>"
            "</section>"
        )
    official_track_html = ""
    if isinstance(official_track, dict) and official_track.get("task_count"):
        official_track_html = (
            "<section><h2>Official Resolution Track</h2>"
            "<p class='muted'>Official evaluator outcomes are deliberately not blended into local strict scores.</p>"
            f"<p>Ranking candidates: <b>{official_track.get('ranking_candidate_task_count')}</b>; "
            f"scorable attempts: <b>{official_track.get('scorable_attempt_count')}</b>; "
            f"resolved attempts: <b>{official_track.get('resolved_attempt_count')}</b>; "
            f"resolution rate: <b>{official_track.get('resolution_rate_percent')}%</b>.</p>"
            f"<p class='muted'>{official_track.get('policy')}</p></section>"
        )
        official_rows = []
        for task in official_track.get("task_outcomes", []):
            if not isinstance(task, dict):
                continue
            official_rows.append(
                "<tr>"
                f"<td><code>{task.get('task_id')}</code></td>"
                f"<td>{task.get('role')}</td>"
                f"<td>{task.get('resolved_attempt_count')} / {task.get('scorable_attempt_count')} / {task.get('attempt_count')}</td>"
                f"<td>{task.get('resolution_rate_percent')}%</td>"
                f"<td>{task.get('classification')}</td>"
                "</tr>"
            )
        official_track_html += (
            "<table><thead><tr><th>Official task</th><th>Role</th><th>Resolved / scorable / attempts</th>"
            "<th>Rate</th><th>Classification</th></tr></thead><tbody>"
            + "".join(official_rows)
            + "</tbody></table>"
        )

    rows = []
    for task in suite_summary.get("tasks", []):
        if _is_official_task(task):
            continue
        rows.append(
            "<tr>"
            f"<td><code>{task.get('task_id')}</code></td>"
            f"<td>{task.get('mean_score')}</td>"
            f"<td>{task.get('mean_verified_normalized_score')}</td>"
            f"<td>{task.get('mean_verified_coverage_percent')}%</td>"
            f"<td>{task.get('mean_duration_seconds')}</td>"
            "</tr>"
        )
    axis_rows = []
    for axis, values in axes.items():
        axis_rows.append(
            "<tr>"
            f"<td>{values.get('title')} (<code>{axis}</code>)</td>"
            f"<td>{values.get('task_count')}</td>"
            f"<td>{values.get('mean_strict_score')}</td>"
            f"<td>{values.get('mean_verified_normalized_score')}</td>"
            f"<td>{values.get('mean_verified_coverage_percent')}%</td>"
            "</tr>"
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Suite Report {suite_summary.get('suite_id')}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2933; }}
    main {{ max-width: 1000px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
    .radar {{ max-width: 420px; }}
    .radar svg {{ width: 100%; height: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; }}
    th, td {{ border-bottom: 1px solid #d8dee4; padding: 8px; text-align: left; }}
    .muted {{ color: #52606d; }}
    @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <h1>Suite: {suite_summary.get('suite_id')}</h1>
  <p class="muted">adapter=<code>{suite_summary.get('adapter')}</code>
    model=<code>{suite_summary.get('model')}</code>
    mean_score=<b>{suite_summary.get('mean_score')}</b>
    tasks={suite_summary.get('task_count')}</p>
  {domain_total_html}
  {decision_index_html}
  {official_track_html}
  <div class="grid">
    <section>
      <h2>Domain-axis radar</h2>
      <p class="muted">Outcome axes (software / systems+embedded / scientific+optics / web / security…)</p>
      <div class="radar">{domain_radar}</div>
    </section>
    <section>
      <h2>Process-dimension radar</h2>
      <p class="muted">Mean of 10 scoring dimensions across suite tasks (when present)</p>
      <div class="radar">{process_radar}</div>
    </section>
  </div>
  <h2>Domain axes</h2>
  <table><thead><tr><th>Axis</th><th>Tasks</th><th>Strict</th><th>Verified</th><th>Coverage</th></tr></thead>
  <tbody>{''.join(axis_rows) or '<tr><td colspan="5">none</td></tr>'}</tbody></table>
  <h2>Tasks</h2>
  <table><thead><tr><th>Task</th><th>Strict</th><th>Verified</th><th>Coverage</th><th>Duration</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
</main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _format_interval(interval: object) -> str:
    if not isinstance(interval, dict):
        return "n/a"
    return f"[{interval.get('lower')}, {interval.get('upper')}] (n={interval.get('n')})"


def _is_official_task(task: object) -> bool:
    return isinstance(task, dict) and isinstance(task.get("task_provenance"), dict) and task["task_provenance"].get("type") == "external_official"
