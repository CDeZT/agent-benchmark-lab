from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VisualCheckResult:
    score: float
    checks: list[dict[str, Any]] = field(default_factory=list)
    engine: str = "html-static-v1"


class _ElementTextParser(HTMLParser):
    def __init__(self, selector: str) -> None:
        super().__init__()
        self.selector = selector
        self._capture_depth = 0
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._capture_depth:
            self._capture_depth += 1
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        if _matches_selector(tag, attrs_dict, self.selector):
            self._capture_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth:
            self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self.text_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(part.strip() for part in self.text_parts if part.strip())


def score_visual_checks(workspace: Path, checks: list[dict[str, Any]]) -> VisualCheckResult:
    if not checks:
        return VisualCheckResult(score=0.0, checks=[], engine="not-configured")

    results = [_run_check(workspace, check) for check in checks]
    passed = sum(1 for result in results if result["passed"])
    score = 100.0 * passed / len(results)
    return VisualCheckResult(score=round(score, 2), checks=results)


def _run_check(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    kind = check.get("type", "")
    if kind == "html_contains_text":
        return _check_html_contains_text(workspace, check)
    if kind == "html_not_contains_text":
        return _check_html_not_contains_text(workspace, check)
    if kind == "html_selector_text":
        return _check_html_selector_text(workspace, check)
    return {"type": kind, "passed": False, "error": f"Unknown visual check type: {kind}", "check": check}


def _check_html_contains_text(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    content, error = _read_html(workspace, check)
    expected = str(check.get("text", ""))
    passed = error is None and expected in content
    return {
        "type": "html_contains_text",
        "path": check.get("path"),
        "text": expected,
        "passed": passed,
        "error": error,
    }


def _check_html_not_contains_text(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    content, error = _read_html(workspace, check)
    forbidden = str(check.get("text", ""))
    passed = error is None and forbidden not in content
    return {
        "type": "html_not_contains_text",
        "path": check.get("path"),
        "text": forbidden,
        "passed": passed,
        "error": error,
    }


def _check_html_selector_text(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    content, error = _read_html(workspace, check)
    selector = str(check.get("selector", ""))
    expected = str(check.get("text", ""))
    actual = ""
    if error is None:
        parser = _ElementTextParser(selector)
        parser.feed(content)
        actual = parser.text
    return {
        "type": "html_selector_text",
        "path": check.get("path"),
        "selector": selector,
        "expected_text": expected,
        "actual_text": actual,
        "passed": error is None and actual == expected,
        "error": error,
    }


def _read_html(workspace: Path, check: dict[str, Any]) -> tuple[str, str | None]:
    relative = check.get("path")
    if not isinstance(relative, str) or not relative:
        return "", "Missing HTML path."
    path = workspace / relative
    if not path.exists():
        return "", f"HTML file not found: {relative}"
    return path.read_text(encoding="utf-8"), None


def _matches_selector(tag: str, attrs: dict[str, str], selector: str) -> bool:
    if selector.startswith("#"):
        return attrs.get("id") == selector[1:]
    if selector.startswith("."):
        classes = attrs.get("class", "").split()
        return selector[1:] in classes
    return tag == selector
