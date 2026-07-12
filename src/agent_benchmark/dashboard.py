from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from agent_benchmark.task_fingerprint import task_fingerprint
from agent_benchmark.task_schema import load_task


def build_dashboard(
    runs_dir: Path,
    *,
    tasks_dir: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Aggregate saved run artifacts into a historical dashboard payload.

    The dashboard never invents scores. It only surfaces JSON that already exists
    under ``runs/`` and labels identity/fingerprint caveats so old debugging
    evidence cannot be mistaken for a selection-ready ranking.
    """
    current_fingerprints = _current_fingerprints(tasks_dir) if tasks_dir else {}
    matrices = _collect_matrices(runs_dir, current_fingerprints=current_fingerprints, limit=limit)
    suites = _collect_suites(runs_dir, current_fingerprints=current_fingerprints, limit=limit)
    tasks = _collect_tasks(runs_dir, current_fingerprints=current_fingerprints, limit=limit)
    bridges = _collect_swebench_bridges(runs_dir, limit=limit)
    return {
        "schema_version": 1,
        "runs_dir": str(runs_dir),
        "policy": {
            "source": "saved artifacts only; no synthetic scores",
            "same_model_requires": "verified_match",
            "cli_default_rows_are_provisional": True,
            "fingerprint_mismatch_excluded_from_current_claims": bool(tasks_dir),
            "limit_per_section": limit,
        },
        "counts": {
            "matrices": len(matrices),
            "suites": len(suites),
            "tasks": len(tasks),
            "swebench_bridges": len(bridges),
        },
        "matrices": matrices,
        "suites": suites,
        "tasks": tasks,
        "swebench_bridges": bridges,
    }


def write_dashboard(
    runs_dir: Path,
    output_dir: Path,
    *,
    tasks_dir: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Write dashboard JSON and a self-contained HTML index."""
    payload = build_dashboard(runs_dir, tasks_dir=tasks_dir, limit=limit)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dashboard.json"
    html_path = output_dir / "index.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_dashboard_html(payload), encoding="utf-8")
    payload["output"] = {"json": str(json_path), "html": str(html_path)}
    return payload


def render_dashboard_html(payload: dict[str, Any]) -> str:
    matrices = payload.get("matrices", [])
    suites = payload.get("suites", [])
    tasks = payload.get("tasks", [])
    bridges = payload.get("swebench_bridges", [])
    counts = payload.get("counts", {})
    policy = payload.get("policy", {})

    matrix_rows = "\n".join(_matrix_row_html(item) for item in matrices) or _empty_row(8)
    suite_rows = "\n".join(_suite_row_html(item) for item in suites) or _empty_row(7)
    task_rows = "\n".join(_task_row_html(item) for item in tasks) or _empty_row(8)
    bridge_rows = "\n".join(_bridge_row_html(item) for item in bridges) or _empty_row(6)

    leaderboard_sections = []
    for matrix in matrices[:10]:
        leaderboard_sections.append(_leaderboard_section_html(matrix))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Agent Benchmark Dashboard</title>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --border: #2d3a4d;
      --text: #e7ecf3;
      --muted: #8b9bb4;
      --accent: #5b9fd4;
      --good: #3d9a6a;
      --warn: #c4922a;
      --bad: #c45c5c;
      --provisional: #8a7a3a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 28px 20px 64px; }}
    h1, h2, h3 {{ font-weight: 650; letter-spacing: -0.02em; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 36px 0 12px; font-size: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    h3 {{ margin: 20px 0 8px; font-size: 16px; color: var(--accent); }}
    p, li {{ color: var(--muted); }}
    code {{ color: #c5d4ea; font-size: 0.92em; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin: 20px 0;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
    .metric b {{ display: block; margin-top: 6px; font-size: 24px; color: var(--text); }}
    .note {{
      background: #1c2430;
      border-left: 3px solid var(--warn);
      padding: 12px 14px;
      border-radius: 0 8px 8px 0;
      margin: 16px 0 24px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; background: #151d29; }}
    tr:last-child td {{ border-bottom: none; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .badge.ok {{ background: rgba(61,154,106,0.18); color: #7dcea0; }}
    .badge.warn {{ background: rgba(196,146,42,0.18); color: #e0c06a; }}
    .badge.bad {{ background: rgba(196,92,92,0.18); color: #e08a8a; }}
    .badge.provisional {{ background: rgba(138,122,58,0.22); color: #d6c57a; }}
    .badge.neutral {{ background: rgba(91,159,212,0.15); color: #9ec5e8; }}
    .muted {{ color: var(--muted); }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .stack {{ display: flex; flex-direction: column; gap: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>Agent Benchmark Dashboard</h1>
  <p>Historical evidence browser for harness × model × task runs. Generated from saved artifacts under <code>{html.escape(str(payload.get("runs_dir", "runs")))}</code>.</p>
  <div class="note">
    <strong>Interpretation rules</strong>
    <ul>
      <li>Strict score is diagnostic; prefer comparable score / verified coverage when present.</li>
      <li>Same-model claims require <code>verified_match</code>. CLI-default rows compare current configurations only.</li>
      <li>Fingerprint mismatches are historical debugging evidence and must not drive selection conclusions.</li>
      <li>SWE-bench <code>error_ids</code> are evaluator infrastructure failures, not model scores.</li>
      <li>Policy: {html.escape(json.dumps(policy, ensure_ascii=False))}</li>
    </ul>
  </div>
  <section class="metrics">
    <div class="metric"><span>Matrices</span><b>{counts.get("matrices", 0)}</b></div>
    <div class="metric"><span>Suites</span><b>{counts.get("suites", 0)}</b></div>
    <div class="metric"><span>Task runs</span><b>{counts.get("tasks", 0)}</b></div>
    <div class="metric"><span>SWE-bench bridges</span><b>{counts.get("swebench_bridges", 0)}</b></div>
  </section>

  <h2>Matrix Runs</h2>
  <table>
    <thead>
      <tr>
        <th>Matrix</th>
        <th>Suite</th>
        <th>Combos</th>
        <th>Top ranked</th>
        <th>Identity</th>
        <th>Fingerprint</th>
        <th>Comparable</th>
        <th>Strict</th>
      </tr>
    </thead>
    <tbody>
      {matrix_rows}
    </tbody>
  </table>

  <h2>Recent Leaderboards</h2>
  {''.join(leaderboard_sections) if leaderboard_sections else '<p class="muted">No matrix leaderboards found.</p>'}

  <h2>Suite Runs</h2>
  <table>
    <thead>
      <tr>
        <th>Suite run</th>
        <th>Suite</th>
        <th>Adapter / model</th>
        <th>Tasks</th>
        <th>Mean strict</th>
        <th>Verified</th>
        <th>Fingerprint</th>
      </tr>
    </thead>
    <tbody>
      {suite_rows}
    </tbody>
  </table>

  <h2>Task Experiments</h2>
  <table>
    <thead>
      <tr>
        <th>Experiment</th>
        <th>Task</th>
        <th>Adapter</th>
        <th>Model</th>
        <th>Mean score</th>
        <th>Verified</th>
        <th>Coverage</th>
        <th>Fingerprint</th>
      </tr>
    </thead>
    <tbody>
      {task_rows}
    </tbody>
  </table>

  <h2>SWE-bench Bridges</h2>
  <table>
    <thead>
      <tr>
        <th>Bridge dir</th>
        <th>Instance</th>
        <th>Resolved</th>
        <th>Scorable</th>
        <th>Classification</th>
        <th>Errors</th>
      </tr>
    </thead>
    <tbody>
      {bridge_rows}
    </tbody>
  </table>
</main>
</body>
</html>
"""


def _collect_matrices(
    runs_dir: Path,
    *,
    current_fingerprints: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("matrix-*/matrix_summary.json"), reverse=True):
        data = _load_json(path)
        if data is None:
            continue
        leaderboard = data.get("leaderboard") if isinstance(data.get("leaderboard"), dict) else {}
        rows = leaderboard.get("rows") if isinstance(leaderboard.get("rows"), list) else []
        ranked = [row for row in rows if row.get("rank") is not None]
        ranked.sort(key=lambda row: int(row.get("rank") or 10**9))
        top = ranked[0] if ranked else None
        fingerprint_state = _matrix_fingerprint_state(data, current_fingerprints)
        items.append(
            {
                "kind": "matrix",
                "matrix_run_id": data.get("matrix_run_id") or path.parent.name,
                "suite_id": data.get("suite_id"),
                "combination_count": data.get("combination_count", len(data.get("combinations") or [])),
                "path": str(path),
                "run_dir": str(path.parent),
                "report_md": str(path.parent / "matrix_report.md") if (path.parent / "matrix_report.md").exists() else None,
                "fingerprint_state": fingerprint_state,
                "leaderboard_rows": rows,
                "top_rank": {
                    "adapter": top.get("adapter"),
                    "model": top.get("model"),
                    "detected_models": top.get("detected_models"),
                    "model_identity_status": top.get("model_identity_status"),
                    "ranking_evidence_state": top.get("ranking_evidence_state"),
                    "mean_comparable_score": top.get("mean_comparable_score"),
                    "mean_strict_score": top.get("mean_strict_score"),
                    "mean_verified_normalized_score": top.get("mean_verified_normalized_score"),
                    "mean_verified_coverage_percent": top.get("mean_verified_coverage_percent"),
                    "rank": top.get("rank"),
                }
                if top
                else None,
            }
        )
        if len(items) >= limit:
            break
    return items


def _collect_suites(
    runs_dir: Path,
    *,
    current_fingerprints: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("suite-*/suite_summary.json"), reverse=True):
        data = _load_json(path)
        if data is None:
            continue
        fingerprint_state = _suite_or_task_list_fingerprint_state(data.get("tasks") or [], current_fingerprints)
        items.append(
            {
                "kind": "suite",
                "suite_run_id": data.get("suite_run_id") or path.parent.name,
                "suite_id": data.get("suite_id"),
                "adapter": data.get("adapter"),
                "model": data.get("model"),
                "adapter_model": data.get("adapter_model"),
                "budget_profile": data.get("budget_profile"),
                "task_count": data.get("task_count"),
                "mean_score": data.get("mean_score"),
                "mean_verified_normalized_score": data.get("mean_verified_normalized_score"),
                "mean_verified_coverage_percent": data.get("mean_verified_coverage_percent"),
                "mean_duration_seconds": data.get("mean_duration_seconds"),
                "path": str(path),
                "run_dir": str(path.parent),
                "fingerprint_state": fingerprint_state,
            }
        )
        if len(items) >= limit:
            break
    return items


def _collect_tasks(
    runs_dir: Path,
    *,
    current_fingerprints: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    # Top-level experiment dirs only; nested suite/matrix copies are redundant.
    for path in sorted(runs_dir.glob("*/summary.json"), reverse=True):
        if path.parent.name.startswith(("matrix-", "suite-", "audit-", "authoritative-", "swebench-", "dashboard")):
            continue
        data = _load_json(path)
        if data is None or "task_id" not in data:
            continue
        task_id = str(data.get("task_id"))
        saved_fp = data.get("task_fingerprint")
        if not current_fingerprints:
            fingerprint_state = "not_checked"
        elif saved_fp is None:
            fingerprint_state = "missing"
        elif saved_fp == current_fingerprints.get(task_id):
            fingerprint_state = "match"
        else:
            fingerprint_state = "mismatch"
        identity = data.get("model_identity") if isinstance(data.get("model_identity"), dict) else {}
        items.append(
            {
                "kind": "task",
                "experiment_id": data.get("experiment_id") or path.parent.name,
                "task_id": task_id,
                "adapter": data.get("adapter"),
                "model": data.get("model"),
                "detected_model": data.get("detected_model"),
                "model_identity_status": identity.get("status"),
                "budget_profile": data.get("budget_profile"),
                "mean_score": data.get("mean_score"),
                "mean_verified_normalized_score": data.get("mean_verified_normalized_score"),
                "mean_verified_coverage_percent": data.get("mean_verified_coverage_percent"),
                "mean_duration_seconds": data.get("mean_duration_seconds"),
                "mean_cost_usd": data.get("mean_cost_usd"),
                "path": str(path),
                "run_dir": str(path.parent),
                "fingerprint_state": fingerprint_state,
            }
        )
        if len(items) >= limit:
            break
    return items


def _collect_swebench_bridges(runs_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("swebench-bridge-*/official_summary.json"), reverse=True):
        data = _load_json(path)
        if data is None:
            continue
        summary = data.get("run_report_summary") if isinstance(data.get("run_report_summary"), dict) else {}
        error_ids = summary.get("error_ids") or []
        resolved = data.get("resolved")
        if error_ids:
            classification = "evaluator_error"
            scorable = False
        elif resolved is True:
            classification = "resolved"
            scorable = True
        elif resolved is False:
            classification = "not_resolved"
            scorable = True
        elif data.get("completed") is False:
            classification = "incomplete"
            scorable = False
        else:
            classification = "unknown"
            scorable = False
        instance_id = None
        submitted = summary.get("submitted_ids") or []
        if submitted:
            instance_id = submitted[0]
        else:
            # Fall back to bridge dir naming: swebench-bridge-<repo>-<num>-timestamp-hash
            instance_id = path.parent.name.replace("swebench-bridge-", "", 1)
        items.append(
            {
                "kind": "swebench_bridge",
                "bridge_dir": str(path.parent),
                "instance_id": instance_id,
                "resolved": resolved,
                "completed": data.get("completed"),
                "scorable": scorable,
                "classification": classification,
                "error_ids": error_ids,
                "path": str(path),
            }
        )
        if len(items) >= limit:
            break
    return items


def _matrix_fingerprint_state(data: dict[str, Any], current_fingerprints: dict[str, str]) -> str:
    if not current_fingerprints:
        return "not_checked"
    states: set[str] = set()
    for combination in data.get("combinations") or []:
        if not isinstance(combination, dict):
            continue
        states.add(_suite_or_task_list_fingerprint_state(combination.get("tasks") or [], current_fingerprints))
    if not states:
        return "missing"
    if states == {"match"}:
        return "match"
    if "mismatch" in states:
        return "mismatch"
    if "missing" in states and "match" in states:
        return "mixed"
    return next(iter(states))


def _suite_or_task_list_fingerprint_state(tasks: list[Any], current_fingerprints: dict[str, str]) -> str:
    if not current_fingerprints:
        return "not_checked"
    if not tasks:
        return "missing"
    states: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id", ""))
        saved = task.get("task_fingerprint")
        if saved is None:
            states.add("missing")
        elif saved == current_fingerprints.get(task_id):
            states.add("match")
        else:
            states.add("mismatch")
    if not states:
        return "missing"
    if states == {"match"}:
        return "match"
    if "mismatch" in states:
        return "mismatch"
    if states == {"missing"}:
        return "missing"
    return "mixed"


def _current_fingerprints(tasks_dir: Path) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    if not tasks_dir.exists():
        return fingerprints
    for path in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        try:
            task = load_task(path)
        except Exception:  # noqa: BLE001 - dashboard should skip malformed tasks.
            continue
        fingerprints[task.task_id] = task_fingerprint(task)
    return fingerprints


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _badge(state: str | None) -> str:
    value = state or "unknown"
    css = {
        "match": "ok",
        "verified_match": "ok",
        "resolved": "ok",
        "default_detected": "provisional",
        "cli_default_model_observed": "provisional",
        "provisional": "provisional",
        "mismatch": "bad",
        "evaluator_error": "bad",
        "not_resolved": "warn",
        "missing": "warn",
        "mixed": "warn",
        "incomplete": "warn",
        "not_checked": "neutral",
        "requested_unverified": "warn",
    }.get(value, "neutral")
    return f'<span class="badge {css}">{html.escape(value)}</span>'


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return html.escape(str(value))


def _empty_row(columns: int) -> str:
    return f'<tr><td colspan="{columns}" class="muted">No saved artifacts found.</td></tr>'


def _matrix_row_html(item: dict[str, Any]) -> str:
    top = item.get("top_rank") or {}
    top_label = "—"
    if top:
        detected = top.get("detected_models") or []
        detected_text = ", ".join(str(x) for x in detected) if detected else str(top.get("model") or "—")
        top_label = f"{html.escape(str(top.get('adapter')))} / {html.escape(detected_text)}"
    return (
        "<tr>"
        f"<td><div class='stack'><code>{html.escape(str(item.get('matrix_run_id')))}</code>"
        f"<span class='muted'>{html.escape(str(item.get('run_dir')))}</span></div></td>"
        f"<td>{html.escape(str(item.get('suite_id') or '—'))}</td>"
        f"<td>{_fmt(item.get('combination_count'), 0)}</td>"
        f"<td>{top_label}</td>"
        f"<td>{_badge(top.get('model_identity_status') if top else None)}</td>"
        f"<td>{_badge(item.get('fingerprint_state'))}</td>"
        f"<td>{_fmt(top.get('mean_comparable_score') if top else None)}</td>"
        f"<td>{_fmt(top.get('mean_strict_score') if top else None)}</td>"
        "</tr>"
    )


def _leaderboard_section_html(matrix: dict[str, Any]) -> str:
    rows = matrix.get("leaderboard_rows") or []
    if not rows:
        return ""
    body = []
    for row in sorted(rows, key=lambda item: int(item.get("rank") or 10**9)):
        detected = row.get("detected_models") or []
        detected_text = ", ".join(str(x) for x in detected) if detected else str(row.get("model") or "—")
        body.append(
            "<tr>"
            f"<td>{_fmt(row.get('rank'), 0)}</td>"
            f"<td>{html.escape(str(row.get('adapter')))}</td>"
            f"<td>{html.escape(detected_text)}</td>"
            f"<td>{_badge(row.get('model_identity_status'))}</td>"
            f"<td>{_badge(row.get('ranking_evidence_state'))}</td>"
            f"<td>{_fmt(row.get('mean_comparable_score'))}</td>"
            f"<td>{_fmt(row.get('mean_strict_score'))}</td>"
            f"<td>{_fmt(row.get('mean_verified_normalized_score'))}</td>"
            f"<td>{_fmt(row.get('mean_verified_coverage_percent'))}%</td>"
            f"<td>{_fmt(row.get('task_pass_rate_percent'))}%</td>"
            f"<td>{_fmt(row.get('mean_duration_seconds'))}s</td>"
            f"<td>{_fmt(row.get('mean_cost_usd'), 4)}</td>"
            "</tr>"
        )
    return f"""
  <h3>{html.escape(str(matrix.get('matrix_run_id')))} · {html.escape(str(matrix.get('suite_id') or ''))} · fingerprint {_badge(matrix.get('fingerprint_state'))}</h3>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Adapter</th><th>Observed model</th><th>Identity</th><th>Evidence</th>
        <th>Comparable</th><th>Strict</th><th>Verified</th><th>Coverage</th><th>Pass</th><th>Duration</th><th>Cost</th>
      </tr>
    </thead>
    <tbody>
      {''.join(body)}
    </tbody>
  </table>
"""


def _suite_row_html(item: dict[str, Any]) -> str:
    model = item.get("detected_model") or item.get("adapter_model") or item.get("model") or "—"
    return (
        "<tr>"
        f"<td><code>{html.escape(str(item.get('suite_run_id')))}</code></td>"
        f"<td>{html.escape(str(item.get('suite_id') or '—'))}</td>"
        f"<td>{html.escape(str(item.get('adapter') or '—'))} / {html.escape(str(model))}</td>"
        f"<td>{_fmt(item.get('task_count'), 0)}</td>"
        f"<td>{_fmt(item.get('mean_score'))}</td>"
        f"<td>{_fmt(item.get('mean_verified_normalized_score'))}</td>"
        f"<td>{_badge(item.get('fingerprint_state'))}</td>"
        "</tr>"
    )


def _task_row_html(item: dict[str, Any]) -> str:
    model = item.get("detected_model") or item.get("model") or "—"
    return (
        "<tr>"
        f"<td><code>{html.escape(str(item.get('experiment_id')))}</code></td>"
        f"<td>{html.escape(str(item.get('task_id') or '—'))}</td>"
        f"<td>{html.escape(str(item.get('adapter') or '—'))}</td>"
        f"<td>{html.escape(str(model))}<div class='muted'>{_badge(item.get('model_identity_status'))}</div></td>"
        f"<td>{_fmt(item.get('mean_score'))}</td>"
        f"<td>{_fmt(item.get('mean_verified_normalized_score'))}</td>"
        f"<td>{_fmt(item.get('mean_verified_coverage_percent'))}%</td>"
        f"<td>{_badge(item.get('fingerprint_state'))}</td>"
        "</tr>"
    )


def _bridge_row_html(item: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td><code>{html.escape(Path(str(item.get('bridge_dir'))).name)}</code></td>"
        f"<td>{html.escape(str(item.get('instance_id') or '—'))}</td>"
        f"<td>{_fmt(item.get('resolved'))}</td>"
        f"<td>{_fmt(item.get('scorable'))}</td>"
        f"<td>{_badge(item.get('classification'))}</td>"
        f"<td>{html.escape(', '.join(str(x) for x in (item.get('error_ids') or [])) or '—')}</td>"
        "</tr>"
    )
