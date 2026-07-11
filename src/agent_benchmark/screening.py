from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from agent_benchmark.corpus_audit import audit_corpus
from agent_benchmark.difficulty import analyze_difficulty
from agent_benchmark.task_schema import build_catalog


_DIFFICULTY_ORDER = {"expert": 0, "hard": 1, "medium": 2, "easy": 3, "unspecified": 4}


def build_screening_report(tasks_dir: Path, runs_dir: Path) -> dict[str, Any]:
    """Separate smoke checks from evidence-backed selection-test candidates.

    Declared difficulty is an authoring hypothesis. A task becomes a local
    screening candidate only after the empirical calibration gate confirms it
    is neither universally easy nor universally impossible.
    """
    catalog = build_catalog(tasks_dir)
    calibration = analyze_difficulty(runs_dir)
    corpus = audit_corpus(tasks_dir)
    empirical = {str(item["task_id"]): item for item in calibration["tasks"]}
    corpus_by_task = {str(item["task_id"]): item for item in corpus["tasks"]}
    tasks = []
    for task in catalog["tasks"]:
        task_id = str(task["id"])
        item = dict(task)
        item["empirical_calibration"] = empirical.get(task_id)
        item["corpus_audit"] = corpus_by_task.get(task_id)
        item["selection_status"] = classify_selection_status(item)
        tasks.append(item)

    tasks.sort(key=lambda task: (_DIFFICULTY_ORDER.get(str(task["difficulty"]), 99), str(task["id"])))
    counts = Counter(str(task["selection_status"]) for task in tasks)
    return {
        "policy": {
            "purpose": "discriminatory screening, not a minimum-pass qualification test",
            "ladder_order": ["expert", "hard", "medium", "easy"],
            "selection_ready_requirements": [
                "comparative_candidate role",
                "baseline/reference corpus audit passes",
                "empirical discriminative_candidate status from identified real-model evidence",
                "three eligible configurations with three repetitions each",
            ],
            "external_import_rule": "external_imported tasks remain source-separated and require their upstream evaluator evidence",
        },
        "summary": {
            "task_count": len(tasks),
            "selection_ready_count": counts["selection_ready_local_seed"],
            "warmup_only_count": counts["warmup_only"],
            "awaiting_real_evidence_count": counts["awaiting_real_evidence"],
            "retune_or_replace_count": counts["retune_or_replace"],
            "official_evaluator_pending_count": counts["official_evaluator_pending"],
            "corpus_gate_pending_count": counts["corpus_gate_pending"],
        },
        "tasks": tasks,
    }


def classify_selection_status(task: dict[str, Any]) -> str:
    """Classify one catalog record without assigning performance points."""
    role = str(task.get("benchmark_role", "comparative_candidate"))
    if role != "comparative_candidate":
        return "warmup_only"

    provenance_type = str(task.get("provenance_type", "unspecified"))
    if provenance_type == "external_imported":
        return "official_evaluator_pending"

    corpus_audit = task.get("corpus_audit")
    if not isinstance(corpus_audit, dict) or corpus_audit.get("classification") != "passes":
        return "corpus_gate_pending"

    empirical = task.get("empirical_calibration")
    classification = empirical.get("classification") if isinstance(empirical, dict) else None
    if classification == "discriminative_candidate":
        return "selection_ready_local_seed"
    if classification in {"too_easy", "too_hard"}:
        return "retune_or_replace"
    return "awaiting_real_evidence"
