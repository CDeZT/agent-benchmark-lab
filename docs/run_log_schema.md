# Run Log Schema

Each benchmark repetition writes `trace.jsonl`. Every line is a JSON object.

## Common Fields

```json
{
  "timestamp": "2026-07-09T00:00:00+00:00",
  "event": "run.started",
  "payload": {}
}
```

## Current Event Types

| Event | Meaning |
| --- | --- |
| `run.started` | A repetition started. |
| `adapter.started` | Adapter execution started. |
| `adapter.finished` | Adapter execution finished. |
| `adapter.failed` | Adapter failed before normal completion. |
| `run.interrupted` | The runner received Ctrl-C and persisted an incomplete repetition for resume. |
| `workspace.changed` | Changed files were detected. |
| `test.public.started` | Public test command started. |
| `test.public.finished` | Public test command finished. |
| `test.hidden.started` | Hidden/private test command started. |
| `test.hidden.finished` | Hidden/private test command finished. |
| `integrity.checked` | Protected file hash integrity was checked. |
| `visual.checked` | Static visual checks were executed. |
| `process.checked` | Process evidence checks were executed. |
| `score.computed` | Scores were computed. |
| `run.finished` | A repetition finished. |

## Planned Event Types

| Event | Meaning |
| --- | --- |
| `adapter.command` | Real harness command invocation. |
| `adapter.output` | Streaming harness output chunk. |
| `plan.detected` | Harness produced a plan. |
| `plan.updated` | Harness updated its plan. |
| `tool.called` | Harness used a tool if observable. |
| `visual.screenshot` | Screenshot captured. |
| `visual.check` | Visual check result. |
| `cost.recorded` | Token or cost information recorded. |
| `integrity.violation` | Test or protected file integrity issue requiring special policy handling. |

## Important Constraint

The trace is evidence, not decoration. Scorers should increasingly depend on trace events as richer metrics are implemented.
