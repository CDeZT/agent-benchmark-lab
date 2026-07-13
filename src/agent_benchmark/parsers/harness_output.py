from __future__ import annotations

"""Parse real harness output to extract model name, tool calls, and usage evidence.

This module extracts structured data from supported harness stdout/stderr so
the scorer can populate dimensions like tool_use and cost_efficiency.
"""

import json
import re
from dataclasses import dataclass, field


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_RAW_ANSI_SUFFIX = re.compile(r"\[\d+(?:;\d+)*m\]?")


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
    if adapter == "mimo":
        return _parse_mimo(stdout, stderr)
    if adapter == "claude-code":
        return _parse_claude_code(stdout, stderr)
    if adapter == "grok":
        return _parse_grok(stdout, stderr)
    if adapter == "codex":
        return _parse_codex(stdout, stderr)
    if adapter == "aider":
        return _parse_aider(stdout, stderr)
    if adapter == "antigravity":
        return _parse_antigravity(stdout, stderr)
    return HarnessEvidence()


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _parse_antigravity(stdout: str, stderr: str) -> HarnessEvidence:
    """Keep AGY print-mode evidence empty until it exposes a stable schema.

    Antigravity CLI 1.1.1 prints a human response, not a documented structured
    event stream.  In particular, text that happens to mention a model, token,
    cost, or shell command is agent-authored content rather than harness
    telemetry, so it must not change benchmark dimensions.
    """
    del stdout, stderr
    return HarnessEvidence()


def normalize_model_name(value: str) -> str:
    """Normalize display artifacts without changing a provider's model identity."""
    return _RAW_ANSI_SUFFIX.sub("", _strip_ansi(value)).strip()


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
    # OpenCode 1.17.15 emits the same structured JSONL shape used by its
    # headless runner. It includes token/cost fields on step-finish events but
    # model identity is retrieved separately from the session export.
    for line in (stdout or "").splitlines():
        event = _load_json_object(line)
        if not isinstance(event, dict):
            continue
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        model = event.get("model") or part.get("model") or part.get("modelID")
        if isinstance(model, str) and model.strip() and evidence.model is None:
            evidence.model = normalize_model_name(model)
        tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
        if evidence.input_tokens is None and isinstance(tokens.get("input"), (int, float)):
            evidence.input_tokens = int(tokens["input"])
        if evidence.output_tokens is None and isinstance(tokens.get("output"), (int, float)):
            evidence.output_tokens = int(tokens["output"])
        cost = part.get("cost") if "cost" in part else event.get("cost")
        if evidence.cost_usd is None and isinstance(cost, (int, float)):
            evidence.cost_usd = float(cost)
        part_type = str(part.get("type") or event.get("type") or "")
        if part_type in {"tool", "tool-call", "tool_call", "function_call"}:
            tool_name = part.get("tool") or part.get("name") or part.get("toolName") or "tool"
            evidence.tool_calls.append({"type": str(tool_name), "detail": str(part)[:200]})
    clean = _strip_ansi(stderr)

    for line in clean.splitlines():
        stripped = line.strip()

        # Model name: "> build · LongCat-2.0" or "> model-name"
        model_match = re.match(r"^>\s*(?:build\s*·\s*)?(.+)$", stripped)
        if model_match and not evidence.model:
            candidate = normalize_model_name(model_match.group(1))
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
    """Extract token counts and cost from a line of text."""
    tokens_match = re.search(r"tokens[:\s]*(\d[\d,]*)\s*in\s*/\s*(\d[\d,]*)\s*out", line, re.I)
    if tokens_match and evidence.input_tokens is None and evidence.output_tokens is None:
        try:
            evidence.input_tokens = int(tokens_match.group(1).replace(",", ""))
            evidence.output_tokens = int(tokens_match.group(2).replace(",", ""))
        except ValueError:
            pass
        return
    input_match = re.search(r"(?:input)[:\s]*(\d[\d,]*)", line, re.I)
    if input_match and evidence.input_tokens is None:
        try:
            evidence.input_tokens = int(input_match.group(1).replace(",", ""))
        except ValueError:
            pass
    output_match = re.search(r"(?:output)[:\s]*(\d[\d,]*)", line, re.I)
    if output_match and evidence.output_tokens is None:
        try:
            evidence.output_tokens = int(output_match.group(1).replace(",", ""))
        except ValueError:
            pass
    cost_match = re.search(r"cost[:\s]*\$?(\d+\.?\d*)", line, re.I)
    if cost_match and evidence.cost_usd is None:
        try:
            evidence.cost_usd = float(cost_match.group(1))
        except ValueError:
            pass


def _parse_mimo(stdout: str, stderr: str) -> HarnessEvidence:
    """Parse MimoCode ``run --format json`` JSONL without guessing identity."""
    evidence = HarnessEvidence()
    for line in (stdout or "").splitlines():
        event = _load_json_object(line)
        if not isinstance(event, dict):
            continue
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        model = event.get("model") or part.get("model") or part.get("modelID")
        if isinstance(model, str) and model.strip() and evidence.model is None:
            evidence.model = normalize_model_name(model)
        tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
        if evidence.input_tokens is None and isinstance(tokens.get("input"), (int, float)):
            evidence.input_tokens = int(tokens["input"])
        if evidence.output_tokens is None and isinstance(tokens.get("output"), (int, float)):
            evidence.output_tokens = int(tokens["output"])
        cost = part.get("cost") if "cost" in part else event.get("cost")
        if evidence.cost_usd is None and isinstance(cost, (int, float)):
            evidence.cost_usd = float(cost)
        part_type = str(part.get("type") or event.get("type") or "")
        if part_type in {"tool", "tool-call", "tool_call", "function_call"}:
            tool_name = part.get("tool") or part.get("name") or part.get("toolName") or "tool"
            evidence.tool_calls.append({"type": str(tool_name), "detail": str(part)[:200]})
    fallback = _parse_opencode("", stderr)
    evidence.model = evidence.model or fallback.model
    evidence.tool_calls.extend(fallback.tool_calls)
    evidence.input_tokens = evidence.input_tokens or fallback.input_tokens
    evidence.output_tokens = evidence.output_tokens or fallback.output_tokens
    evidence.cost_usd = evidence.cost_usd if evidence.cost_usd is not None else fallback.cost_usd
    return evidence


def _parse_grok(stdout: str, stderr: str) -> HarnessEvidence:
    """Parse Grok Build headless JSON/plain output.

    Documented JSON success shape includes ``text`` / ``sessionId``. Usage fields
    are optional and only scored when present so missing telemetry degrades
    gracefully instead of inventing cost or tool evidence.
    """
    evidence = HarnessEvidence()
    for blob in (stdout, stderr):
        payload = _load_json_object(blob)
        if payload is None:
            continue
        if payload.get("type") == "error":
            continue
        model = payload.get("model") or payload.get("modelId") or payload.get("model_id")
        if isinstance(model, str) and model.strip():
            evidence.model = model.strip()
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        for key, attr in (
            ("input_tokens", "input_tokens"),
            ("inputTokens", "input_tokens"),
            ("prompt_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("outputTokens", "output_tokens"),
            ("completion_tokens", "output_tokens"),
        ):
            value = usage.get(key) if key in usage else payload.get(key)
            if isinstance(value, (int, float)) and getattr(evidence, attr) is None:
                setattr(evidence, attr, int(value))
        for key in ("cost_usd", "total_cost_usd", "cost"):
            value = usage.get(key) if key in usage else payload.get(key)
            if isinstance(value, (int, float)) and evidence.cost_usd is None:
                evidence.cost_usd = float(value)
        tools = payload.get("toolCalls") or payload.get("tool_calls") or payload.get("tools")
        if isinstance(tools, list):
            for item in tools:
                if isinstance(item, dict):
                    evidence.tool_calls.append(
                        {
                            "type": str(item.get("type") or item.get("name") or "tool"),
                            "detail": str(item.get("name") or item.get("id") or item)[:200],
                        }
                    )
                elif isinstance(item, str) and item.strip():
                    evidence.tool_calls.append({"type": "tool", "detail": item.strip()[:200]})
        if evidence.model or evidence.tool_calls or evidence.input_tokens is not None:
            return evidence
    # Streaming-json: collect the same optional telemetry event by event.
    for line in (stdout or "").splitlines():
        event = _load_json_object(line)
        if not isinstance(event, dict):
            continue
        model = event.get("model") or event.get("modelId") or event.get("model_id")
        if isinstance(model, str) and model.strip() and evidence.model is None:
            evidence.model = normalize_model_name(model)
        usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        if evidence.input_tokens is None:
            value = usage.get("input_tokens", usage.get("inputTokens", event.get("input_tokens")))
            if isinstance(value, (int, float)):
                evidence.input_tokens = int(value)
        if evidence.output_tokens is None:
            value = usage.get("output_tokens", usage.get("outputTokens", event.get("output_tokens")))
            if isinstance(value, (int, float)):
                evidence.output_tokens = int(value)
        if evidence.cost_usd is None:
            value = usage.get("cost_usd", usage.get("cost", event.get("cost_usd", event.get("cost"))))
            if isinstance(value, (int, float)):
                evidence.cost_usd = float(value)
        event_type = str(event.get("type") or "")
        if event_type in {"tool", "tool_call", "toolCall", "function_call"}:
            tool_name = event.get("name") or event.get("tool") or event_type
            evidence.tool_calls.append({"type": str(tool_name), "detail": str(event)[:200]})
    return evidence


def _parse_codex(stdout: str, stderr: str) -> HarnessEvidence:
    """Parse Codex ``exec --json`` JSONL without inferring absent telemetry."""
    evidence = HarnessEvidence()
    for line in (stdout or "").splitlines():
        event = _load_json_object(line)
        if not isinstance(event, dict):
            continue
        evidence.model = evidence.model or _first_string(event, ("model", "model_name", "modelName"))
        _extract_usage(event.get("usage"), evidence)
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "")
        if item_type == "command_execution":
            command = item.get("command")
            if isinstance(command, str) and command.strip():
                evidence.tool_calls.append({"type": "bash", "command": command.strip()[:500]})
        elif item_type == "file_change":
            changes = item.get("changes")
            if isinstance(changes, list):
                for change in changes:
                    if isinstance(change, dict):
                        path = change.get("path") or change.get("file")
                        evidence.tool_calls.append(
                            {"type": "edit", "path": str(path)[:500] if path is not None else "unknown"}
                        )
    for line in (stderr or "").splitlines():
        _extract_token_cost(line, evidence)
    return evidence


def _parse_aider(stdout: str, stderr: str) -> HarnessEvidence:
    """Extract only explicitly printed Aider model, token, and cost telemetry."""
    evidence = HarnessEvidence()
    for line in (stdout + "\n" + stderr).splitlines():
        model_match = re.match(r"^\s*Models?\s*:\s*([^,]+)", line, re.I)
        if model_match and evidence.model is None:
            evidence.model = model_match.group(1).strip()
        _extract_token_cost(line, evidence)
    return evidence


def _extract_usage(payload: object, evidence: HarnessEvidence) -> None:
    if not isinstance(payload, dict):
        return
    evidence.input_tokens = evidence.input_tokens or _first_int(payload, ("input_tokens", "inputTokens", "prompt_tokens"))
    evidence.output_tokens = evidence.output_tokens or _first_int(payload, ("output_tokens", "outputTokens", "completion_tokens"))
    evidence.cost_usd = evidence.cost_usd if evidence.cost_usd is not None else _first_float(
        payload, ("cost_usd", "total_cost_usd", "cost")
    )


def _load_json_object(text: str) -> dict | None:
    if not text or not text.strip():
        return None
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        # Some CLIs print logs before the final JSON object.
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except (TypeError, json.JSONDecodeError):
            return None
    return payload if isinstance(payload, dict) else None


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

    # API errors often name the configured model even when the run never starts.
    result_text = payload.get("result")
    if evidence.model is None and isinstance(result_text, str):
        model_match = re.search(r"model=([^\s)\]\"']+)", result_text)
        if model_match:
            evidence.model = model_match.group(1).strip()

    model_usage = payload.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        model_name_pairs = [
            (str(name), normalize_model_name(str(name)))
            for name in model_usage
            if normalize_model_name(str(name))
        ]
        model_names = [normalized for _, normalized in model_name_pairs]
        if evidence.model is None and len(model_names) == 1:
            evidence.model = model_names[0]
        if evidence.cost_usd is None and len(model_names) == 1:
            usage_details = model_usage.get(model_name_pairs[0][0])
            if isinstance(usage_details, dict):
                evidence.cost_usd = _first_float(usage_details, ("costUSD", "cost_usd"))

    if isinstance(usage, dict):
        server_tool_use = usage.get("server_tool_use")
        if isinstance(server_tool_use, dict):
            for tool_name, count in server_tool_use.items():
                if isinstance(count, int) and count > 0:
                    evidence.tool_calls.extend({"type": f"server_{tool_name}"} for _ in range(count))

    # num_turns: each turn beyond the first involves at least one tool interaction.
    num_turns = payload.get("num_turns")
    if isinstance(num_turns, int) and num_turns > 1:
        agent_turns = num_turns - 1
        evidence.tool_calls.append({"type": "interaction", "turns": num_turns})
        evidence.tool_calls.extend({"type": "agent_turn"} for _ in range(agent_turns))

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
            return normalize_model_name(value)
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
