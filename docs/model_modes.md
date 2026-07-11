# Model Comparison Modes

Model names in this project are deliberately not fixed. The user may change the
model configured behind Claude Code or opencode at any time. A benchmark run
must record the configuration and observed output at that moment instead of
silently assuming a model from an old registry entry or report label.

## CLI Default Configuration Mode

This is the normal, first-class mode for day-to-day selection. Leave
`--models` as its default `unspecified` value:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite calibration --adapters opencode,claude-code --models unspecified --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix \
  --suite calibration --adapters opencode,claude-code --models unspecified --repetitions 3
```

Each adapter uses its current CLI-configured default. The run is a comparison
of complete current configurations: harness plus whichever model each CLI is
actually using. It is valid for practical tool selection, but it is never a
claim that both harnesses used the same model. Reports label this mode as
`cli_default_configurations` and preserve any detected model identities. If a
CLI does not expose its model identity, the result remains usable as a current
configuration measurement but is labelled `default_unverified`.

## Explicit Same-Model Mode

Use an explicit canonical model and an adapter-specific registry only when the
question really is "which harness is stronger with the same model?":

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix \
  --suite calibration --adapters opencode,claude-code \
  --models your-canonical-model --model-registry config/your-models.json --repetitions 3
```

The registry solves naming differences; it does not prove that a CLI selected
the requested model. A same-model conclusion is allowed only where saved
harness output gives `model_identity.status=verified_match`. If an adapter can
only use its configured default, preflight warns that the explicit selection
is external to this command.

## Interpretation Rule

Do not convert a requested label, registry mapping, or yesterday's CLI setting
into a model fact. Use the saved `model_identity`, detected model list, CLI
version, task evidence, and run timestamp for every result. Re-run the
default-configuration matrix after changing either CLI's model setting.
