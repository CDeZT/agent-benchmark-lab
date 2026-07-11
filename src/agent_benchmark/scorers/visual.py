from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

@dataclass(frozen=True)
class VisualCheckResult:
    score: float
    checks: list[dict[str, Any]] = field(default_factory=list)
    engine: str = "html-static-v1"
    verified: bool = False


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


def score_visual_checks(
    workspace: Path,
    checks: list[dict[str, Any]],
    artifacts_dir: Path | None = None,
) -> VisualCheckResult:
    if not checks:
        return VisualCheckResult(score=0.0, checks=[], engine="not-configured", verified=False)

    results = [_run_check(workspace, check, artifacts_dir, index) for index, check in enumerate(checks, start=1)]
    passed = sum(1 for result in results if result["passed"])
    score = 100.0 * passed / len(results)
    engines = sorted({str(result.get("engine", "html-static-v1")) for result in results})
    verified = all(result.get("measurement_status") == "verified" for result in results)
    return VisualCheckResult(
        score=round(score, 2),
        checks=results,
        engine="+".join(engines),
        verified=verified,
    )


def _run_check(workspace: Path, check: dict[str, Any], artifacts_dir: Path | None, index: int) -> dict[str, Any]:
    kind = check.get("type", "")
    if kind == "html_contains_text":
        return _check_html_contains_text(workspace, check)
    if kind == "html_not_contains_text":
        return _check_html_not_contains_text(workspace, check)
    if kind == "html_selector_text":
        return _check_html_selector_text(workspace, check)
    if kind == "browser_screenshot":
        return _check_browser_screenshot(workspace, check, artifacts_dir, index)
    return {
        "type": kind,
        "engine": "unknown",
        "measurement_status": "unavailable",
        "passed": False,
        "error": f"Unknown visual check type: {kind}",
        "check": check,
    }


def _check_html_contains_text(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    content, error = _read_html(workspace, check)
    expected = str(check.get("text", ""))
    passed = error is None and expected in content
    return {
        "type": "html_contains_text",
        "engine": "html-static-v1",
        "measurement_status": "verified",
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
        "engine": "html-static-v1",
        "measurement_status": "verified",
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
        "engine": "html-static-v1",
        "measurement_status": "verified",
        "path": check.get("path"),
        "selector": selector,
        "expected_text": expected,
        "actual_text": actual,
        "passed": error is None and actual == expected,
        "error": error,
    }


def _check_browser_screenshot(
    workspace: Path,
    check: dict[str, Any],
    artifacts_dir: Path | None,
    index: int,
) -> dict[str, Any]:
    relative = check.get("path")
    if not isinstance(relative, str) or not relative:
        return _browser_error(check, "Missing HTML path.", "unavailable")
    page_path = workspace / relative
    if not page_path.is_file():
        return _browser_error(check, f"HTML file not found: {relative}", "verified")
    if not shutil.which("node"):
        return _browser_error(check, "Node.js is required for browser screenshot checks.", "unavailable")

    viewport = check.get("viewport", {})
    if not isinstance(viewport, dict):
        return _browser_error(check, "viewport must be an object.", "unavailable")
    width = int(viewport.get("width", 1280))
    height = int(viewport.get("height", 720))
    selectors = check.get("required_selectors", [])
    if not isinstance(selectors, list) or not all(isinstance(selector, str) and selector for selector in selectors):
        return _browser_error(check, "required_selectors must be a list of non-empty selectors.", "unavailable")

    artifact_root = artifacts_dir or workspace.parent / "visual"
    artifact_root.mkdir(parents=True, exist_ok=True)
    screenshot_path = artifact_root / f"screenshot-{index}.png"
    script = Path(__file__).resolve().parents[3] / "scripts" / "capture_browser_screenshot.mjs"
    if not script.is_file():
        return _browser_error(check, f"Browser capture script is missing: {script}", "unavailable")

    timeout_seconds = float(check.get("timeout_seconds", 30))
    command = [
        "node",
        str(script),
        "--url", page_path.resolve().as_uri(),
        "--output", str(screenshot_path),
        "--width", str(width),
        "--height", str(height),
        "--timeout-ms", str(round(timeout_seconds * 1000)),
        "--selectors", json.dumps(selectors),
    ]
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds + 10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _browser_error(check, f"Browser capture timed out after {timeout_seconds} seconds.", "verified")
    if completed.returncode:
        return _browser_error(check, completed.stderr[-2000:] or "Browser capture failed.", "unavailable")
    try:
        browser_evidence = json.loads(completed.stdout)
        pixel_evidence = _pixel_evidence(screenshot_path, check)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _browser_error(check, f"Could not inspect browser screenshot: {exc}", "unavailable")
    except ModuleNotFoundError:
        return _browser_error(check, "Pillow is required for browser pixel inspection.", "unavailable")

    selector_results = browser_evidence.get("selectors", {})
    all_visible = all(selector_results.get(selector) is True for selector in selectors)
    passed = all_visible and pixel_evidence["passed"]
    return {
        "type": "browser_screenshot",
        "engine": "playwright-chromium-v1",
        "measurement_status": "verified",
        "path": relative,
        "screenshot_path": str(screenshot_path),
        "viewport": browser_evidence.get("viewport"),
        "selector_visibility": selector_results,
        "pixel": pixel_evidence,
        "passed": passed,
        "error": None if passed else "One or more required selectors were hidden or the pixel threshold failed.",
    }


def _browser_error(check: dict[str, Any], error: str, measurement_status: str) -> dict[str, Any]:
    return {
        "type": "browser_screenshot",
        "engine": "playwright-chromium-v1",
        "measurement_status": measurement_status,
        "path": check.get("path"),
        "passed": False,
        "error": error,
    }


def _pixel_evidence(path: Path, check: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image, ImageStat

    with Image.open(path) as source:
        image = source.convert("RGB")
    background = _hex_color(str(check.get("background", "#ffffff")))
    threshold = int(check.get("pixel_distance_threshold", 20))
    min_non_background = int(check.get("min_non_background_pixels", 1))
    min_stddev = float(check.get("min_channel_stddev", 0.0))
    pixels = image.get_flattened_data()
    non_background = sum(
        1
        for pixel in pixels
        if sum((component - baseline) ** 2 for component, baseline in zip(pixel, background, strict=True)) ** 0.5 >= threshold
    )
    channel_stddev = [round(value, 4) for value in ImageStat.Stat(image).stddev]
    passed = non_background >= min_non_background and max(channel_stddev, default=0.0) >= min_stddev
    return {
        "size": {"width": image.width, "height": image.height},
        "background": "#%02x%02x%02x" % background,
        "pixel_distance_threshold": threshold,
        "non_background_pixels": non_background,
        "min_non_background_pixels": min_non_background,
        "channel_stddev": channel_stddev,
        "min_channel_stddev": min_stddev,
        "passed": passed,
    }


def _hex_color(value: str) -> tuple[int, int, int]:
    candidate = value.removeprefix("#")
    if len(candidate) != 6:
        raise ValueError("background must be a #RRGGBB color")
    return tuple(int(candidate[index:index + 2], 16) for index in range(0, 6, 2))


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
