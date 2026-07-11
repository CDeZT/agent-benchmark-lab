from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any


def write_html_report(path: Path, summary: dict[str, Any]) -> None:
    first_run = summary["runs"][0] if summary["runs"] else {"dimensions": {}}
    dimensions = first_run.get("dimensions", {})
    measurement = first_run.get("measurement", {})
    statuses = measurement.get("dimension_status", {}) if isinstance(measurement, dict) else {}
    radar = _radar_svg(dimensions)
    weights = {
        "task_completion": 30, "intent_understanding": 10, "planning": 8,
        "execution_quality": 12, "self_repair": 10, "test_discipline": 10,
        "tool_use": 6, "visual_verification": 4, "safety_boundary": 6,
        "cost_efficiency": 4,
    }
    bars = "\n".join(
        f"<div class='bar'><span>{html.escape(name)} ({weights.get(name, 0)}%, {html.escape(str(statuses.get(name, 'unavailable')))})</span><meter min='0' max='100' value='{value}'></meter><b>{value:.1f}</b></div>"
        for name, value in dimensions.items()
    )
    run_rows = "\n".join(
        f"<tr><td>{run['repetition']}</td><td>{run['score']}</td><td>{_status(run['public_test_passed'])}</td>"
        f"<td>{_status(run['hidden_test_passed'])}</td><td>{run.get('tool_call_count', 0)}</td>"
        f"<td>{run['duration_seconds']}</td><td>{html.escape(', '.join(run['changed_files']) or 'none')}</td></tr>"
        for run in summary["runs"]
    )
    detected = summary.get("detected_model")
    model_display = html.escape(summary['model']) + (f" (detected: {html.escape(detected)})" if detected and detected != summary["model"] else "")
    model_identity = summary.get("model_identity")
    model_status = model_identity.get("status", "not-recorded") if isinstance(model_identity, dict) else "not-recorded"
    total_tools = summary.get("total_tool_calls", 0)
    score_interval = _format_interval(summary.get("score_confidence_interval_95"))
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Benchmark Report {html.escape(summary['task_id'])}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2933; }}
    main {{ max-width: 960px; margin: 0 auto; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 12px; }}
    .metric span {{ display: block; color: #52606d; font-size: 13px; }}
    .metric b {{ font-size: 24px; }}
    .metric.ci b {{ font-size: 16px; overflow-wrap: anywhere; }}
    .bar {{ display: grid; grid-template-columns: 220px 1fr 64px; gap: 12px; align-items: center; margin: 8px 0; }}
    meter {{ width: 100%; height: 18px; }}
    .radar {{ max-width: 520px; margin: 16px 0 28px; }}
    .radar svg {{ width: 100%; height: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
    th, td {{ border-bottom: 1px solid #d8dee4; padding: 10px; text-align: left; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(summary['task_title'])}</h1>
  <p><code>{html.escape(summary['task_id'])}</code> with adapter <code>{html.escape(summary['adapter'])}</code>, model <code>{model_display}</code>, profile <code>{html.escape(summary['budget_profile'])}</code></p>
  <section class="summary">
    <div class="metric"><span>Model identity</span><b>{html.escape(str(model_status))}</b></div>
    <div class="metric"><span>Mean</span><b>{summary['mean_score']}</b></div>
    <div class="metric ci"><span>Score 95% CI</span><b>{html.escape(score_interval)}</b></div>
    <div class="metric"><span>Verified normalized</span><b>{summary.get('mean_verified_normalized_score')}</b></div>
    <div class="metric"><span>Verified coverage</span><b>{summary.get('mean_verified_coverage_percent')}%</b></div>
    <div class="metric"><span>Variance</span><b>{summary['variance']}</b></div>
    <div class="metric"><span>Best</span><b>{summary['best_score']}</b></div>
    <div class="metric"><span>Worst</span><b>{summary['worst_score']}</b></div>
    <div class="metric"><span>Mean seconds</span><b>{summary['mean_duration_seconds']}</b></div>
    <div class="metric"><span>Tool calls</span><b>{total_tools}</b></div>
  </section>
  <h2>Radar Snapshot</h2>
  <div class="radar">{radar}</div>
  <h2>Dimension Scores</h2>
  {bars}
  <h2>Runs</h2>
  <table><thead><tr><th>Rep</th><th>Score</th><th>Public</th><th>Hidden</th><th>Tools</th><th>Duration</th><th>Changed Files</th></tr></thead><tbody>{run_rows}</tbody></table>
</main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _status(value: object) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "n/a"


def _format_interval(interval: object) -> str:
    if not isinstance(interval, dict):
        return "n/a"
    return f"[{interval.get('lower')}, {interval.get('upper')}]"


def _radar_svg(dimensions: dict[str, float]) -> str:
    if not dimensions:
        return "<p>No dimensions available.</p>"
    labels = list(dimensions)
    values = [max(0.0, min(100.0, float(dimensions[label]))) for label in labels]
    center = 180
    radius = 120
    points = []
    label_nodes = []
    axis_lines = []
    for index, (label, value) in enumerate(zip(labels, values)):
        angle = -math.pi / 2 + (2 * math.pi * index / len(labels))
        outer_x = center + radius * math.cos(angle)
        outer_y = center + radius * math.sin(angle)
        value_radius = radius * (value / 100.0)
        point_x = center + value_radius * math.cos(angle)
        point_y = center + value_radius * math.sin(angle)
        label_x = center + (radius + 34) * math.cos(angle)
        label_y = center + (radius + 34) * math.sin(angle)
        points.append(f"{point_x:.1f},{point_y:.1f}")
        axis_lines.append(f"<line x1='{center}' y1='{center}' x2='{outer_x:.1f}' y2='{outer_y:.1f}' />")
        label_nodes.append(
            f"<text x='{label_x:.1f}' y='{label_y:.1f}' text-anchor='middle'>{html.escape(label)}</text>"
        )
    polygon = " ".join(points)
    rings = "\n".join(
        f"<circle cx='{center}' cy='{center}' r='{radius * step / 4:.1f}' />"
        for step in range(1, 5)
    )
    return f"""
<svg viewBox="0 0 360 360" role="img" aria-label="Radar chart">
  <style>
    circle, line {{ fill: none; stroke: #d8dee4; stroke-width: 1; }}
    polygon {{ fill: rgba(28, 126, 214, 0.26); stroke: #1c7ed6; stroke-width: 2; }}
    text {{ font-size: 10px; fill: #52606d; }}
  </style>
  {rings}
  {''.join(axis_lines)}
  <polygon points="{polygon}" />
  {''.join(label_nodes)}
</svg>
"""
