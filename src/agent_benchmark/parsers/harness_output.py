from __future__ import annotations

"""Parse real harness output to extract model name, tool calls, and usage evidence.

This module extracts structured data from opencode and claude-code stdout/stderr
so the scorer can populate dimensions like tool_use and cost_efficiency.
"""

import json
import re
from dataclasses import dataclass, field


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class HarnessEvidence:
    model: str | None = None
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def parse_harness_output(adapter: str, stdout: str, stderr: str) -> HarnessEvidence:
    """Parse harness output and return structured evidence."""
    if adapter == "opencode":
        return _parse_opencode(stdout, stderr)
    if adapter == "claude-code":
        return _parse_claude_code(stdout, stderr)
    return HarnessEvidence()


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _parse_opencode(stdout: str, stderr: str) -> HarnessEvidence:
    """Parse opencode output.

    opencode writes tool activity to stderr in this format:
        > build · LongCat-2.0          # model name
        → Read file.py                 # read tool
        ← Edit file.py                 # edit tool
        ✱ Grep "pattern" in . · N      # search tool
        $ command                      # shell command

    Token/cost may appear in summary lines like:
        Tokens: 1,234 in / 567 out
        Cost: $0.0123
        Input tokens: 1234
        Output tokens: 567
    """
    evidence = HarnessEvidence()
    clean = _strip_ansi(stderr)

    for line in clean.splitlines():
        stripped = line.strip()

        # Model name: "> build · LongCat-2.0" or "> model-name"
        model_match = re.match(r"^>\s*(?:build\s*·\s*)?(.+)$", stripped)
        if model_match and not evidence.model:
            candidate = model_match.group(1).strip()
            if candidate and not candidate.startswith("$"):
                evidence.model = candidate

        # Read tool: "→ Read file.py"
        if stripped.startswith("→") and "Read" in stripped:
            path = _extract_path(stripped, "Read")
            if path:
                evidence.tool_calls.append({"type": "read", "path": path})

        # Edit tool: "← Edit file.py"
        if stripped.startswith("←") and "Edit" in stripped:
            path = _extract_path(stripped, "Edit")
            if path:
                evidence.tool_calls.append({"type": "edit", "path": path})

        # Search/grep tool: "✱ Grep "pattern""
        if stripped.startswith("✱") and ("Grep" in stripped or "Search" in stripped):
            evidence.tool_calls.append({"type": "search", "detail": stripped})

        # Shell command: "$ command"
        if re.match(r"^\$\s+", stripped):
            cmd = stripped[2:].strip()
            if cmd:
                evidence.tool_calls.append({"type": "bash", "command": cmd})

        # Token/cost parsing
        _extract_token_cost(stripped, evidence)

    return evidence


def _extract_token_cost(line: str, evidence: HarnessEvidence) -> None:
    """Extract token counts and cost from a line of text.

    Handles various formats:
        Tokens: 1,234 in / 567 out
        Input tokens: 1234
        Output tokens: 567
        Cost: $0.0123
        Total cost: $0.05
    """
    # Format: "Tokens: 1,234 in / 567 out"
    tokens_match = re.search(r"tokens[:\s]*(\d[\d,]*)\s*in\s*/\s*(\d[\d,]*)\s*out", line, re.I)
    if tokens_match and evidence.input_tokens is None and evidence.output_tokens is None:
        try:
            evidence.input_tokens = int(tokens_match.group(1).replace(",", ""))
            evidence.output_tokens = int(tokens_match.group(2).replace(",", ""))
        except ValueError:
            pass
        return

    # Input tokens (standalone)
    input_match = re.search(r"(?:input)[:\s]*(\d[\d,]*)", line, re.I)
    if input_match and evidence.input_tokens is None:
        try:
            evidence.input_tokens = int(input_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Output tokens (standalone)
    output_match = re.search(r"(?:output)[:\s]*(\d[\d,]*)", line, re.I)
    if output_match and evidence.output_tokens is None:
        try:
            evidence.output_tokens = int(output_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Cost in USD
    cost_match = re.search(r"cost[:\s]*\$?(\d+\.?\d*)", line, re.I)
    if cost_match and evidence.cost_usd is None:
        try:
            evidence.cost_usd = float(cost_match.group(1))
        except ValueError:
            pass


def _parse_claude_code(stdout: str, stderr: str) -> HarnessEvidence:
    """Parse claude-code output.

    claude-code writes the final summary to stdout. Tool calls and model info
    are not consistently exposed in stdout/stderr for the -p (print) mode.
    We extract what we can from the output text.
    """
    evidence = HarnessEvidence()

    structured = _parse_claude_json(stdout)
    if structured is not None:
        return structured

    # Fall back to the plain-text mode used by custom adapter templates.

    # Count tool-like patterns in the output as rough evidence
    # claude-code sometimes mentions what it did in the summary
    summary = stdout.strip()

    # Look for file modification indicators
    edit_patterns = re.findall(r"(`[^`]+\.py`|`[^`]+\.c`|`[^`]+\.js`|`[^`]+\.ts`|`[^`]+\.html`)", summary)
    for match in edit_patterns:
        path = match.strip("`")
        if "/" not in path:  # Likely a filename reference, not a path
            evidence.tool_calls.append({"type": "reference", "path": path})

    return evidence


def _parse_claude_json(stdout: str) -> HarnessEvidence | None:
    """Parse Claude Code's documented ``--output-format json`` result object."""
    try:
        payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    evidence = HarnessEvidence()
    evidence.model = _first_string(payload, ("model", "model_name", "modelName"))
    usage = payload.get("usage")
    if isinstance(usage, dict):
        evidence.model = evidence.model or _first_string(usage, ("model", "model_name", "modelName"))
        evidence.input_tokens = _first_int(usage, ("input_tokens", "inputTokens", "input"))
        evidence.output_tokens = _first_int(usage, ("output_tokens", "outputTokens", "output"))
    evidence.input_tokens = evidence.input_tokens or _first_int(payload, ("input_tokens", "inputTokens"))
    evidence.output_tokens = evidence.output_tokens or _first_int(payload, ("output_tokens", "outputTokens"))
    evidence.cost_usd = _first_float(payload, ("total_cost_usd", "cost_usd", "totalCostUsd", "costUsd"))
    if evidence.cost_usd is None and isinstance(usage, dict):
        evidence.cost_usd = _first_float(usage, ("total_cost_usd", "cost_usd", "totalCostUsd", "costUsd"))

    model_usage = payload.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        model_names = [str(name).strip() for name in model_usage if str(name).strip()]
        if evidence.model is None and len(model_names) == 1:
            evidence.model = model_names[0]
        if evidence.cost_usd is None and len(model_names) == 1:
            usage_details = model_usage.get(model_names[0])
            if isinstance(usage_details, dict):
                evidence.cost_usd = _first_float(usage_details, ("costUSD", "cost_usd"))

    if isinstance(usage, dict):
        server_tool_use = usage.get("server_tool_use")
        if isinstance(server_tool_use, dict):
            for tool_name, count in server_tool_use.items():
                if isinstance(count, int) and count > 0:
                    evidence.tool_calls.extend({"type": f"server_{tool_name}"} for _ in range(count))

    # The final text can still mention files, which is only heuristic tool use.
    result = payload.get("result")
    if isinstance(result, str):
        for match in re.findall(r"(`[^`]+\.(?:py|c|js|ts|html)`)", result):
            evidence.tool_calls.append({"type": "reference", "path": match.strip("`")})
    return evidence


def _first_string(payload: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(payload: dict[str, object], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.replace(",", "").isdigit():
            return int(value.replace(",", ""))
    return None


def _first_float(payload: dict[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.removeprefix("$"))
            except ValueError:
                continue
    return None


def _extract_path(line: str, keyword: str) -> str | None:
    """Extract file path from a tool call line like '→ Read path/to/file'."""
    parts = line.split(keyword, 1)
    if len(parts) < 2:
        return None
    path = parts[1].strip()
    # Remove ANSI artifacts and trailing markers
    path = path.split("·")[0].strip()
    path = path.split("in ")[0].strip()
    return path if path else None
