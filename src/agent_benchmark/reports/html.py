from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any


def write_html_report(path: Path, summary: dict[str, Any]) -> None:
    first_run = summary["runs"][0] if summary["runs"] else {"dimensions": {}}
    dimensions = first_run.get("dimensions", {})
    radar = _radar_svg(dimensions)
    bars = "\n".join(
        f"<div class='bar'><span>{html.escape(name)}</span><meter min='0' max='100' value='{value}'></meter><b>{value:.1f}</b></div>"
        for name, value in dimensions.items()
    )
    run_rows = "\n".join(
        f"<tr><td>{run['repetition']}</td><td>{run['score']}</td><td>{_status(run['public_test_passed'])}</td>"
        f"<td>{_status(run['hidden_test_passed'])}</td><td>{html.escape(', '.join(run['changed_files']) or 'none')}</td></tr>"
        for run in summary["runs"]
    )
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
  <p><code>{html.escape(summary['task_id'])}</code> with adapter <code>{html.escape(summary['adapter'])}</code>, model <code>{html.escape(summary['model'])}</code>, profile <code>{html.escape(summary['budget_profile'])}</code></p>
  <section class="summary">
    <div class="metric"><span>Mean</span><b>{summary['mean_score']}</b></div>
    <div class="metric"><span>Variance</span><b>{summary['variance']}</b></div>
    <div class="metric"><span>Best</span><b>{summary['best_score']}</b></div>
    <div class="metric"><span>Worst</span><b>{summary['worst_score']}</b></div>
    <div class="metric"><span>Mean seconds</span><b>{summary['mean_duration_seconds']}</b></div>
  </section>
  <h2>Radar Snapshot</h2>
  <div class="radar">{radar}</div>
  <h2>Dimension Scores</h2>
  {bars}
  <h2>Runs</h2>
  <table><thead><tr><th>Repetition</th><th>Score</th><th>Public</th><th>Hidden</th><th>Changed Files</th></tr></thead><tbody>{run_rows}</tbody></table>
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
