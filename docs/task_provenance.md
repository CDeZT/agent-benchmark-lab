# Task Provenance

This file records where benchmark tasks come from and how strongly they can be treated as external benchmark evidence.

## Current Classification

The current task set is a project-owned seed corpus. It is useful for validating the framework, adapters, scoring, hidden tests, and early harness/model comparisons. It is not yet an imported authoritative benchmark corpus.

| Category | Meaning | Current Status |
| --- | --- | --- |
| `custom_seed` | Designed inside this repository to exercise one capability or domain. | Most current tasks. |
| `domain_seed` | Custom seed task specialized for embedded, optics, systems, data, or full-stack work. | Embedded, optics, C systems, data pipeline, full-stack tasks. |
| `inspired_by_external` | Custom task inspired by public benchmark patterns, without copying external benchmark data. | `python-swebench-style` and the `advanced` suite wording. |
| `external_imported` | A task imported or converted from a named external benchmark with preserved provenance. | Not implemented yet. |

## Important Boundary

Do not describe current tasks as "authoritative imported tasks." The accurate wording is:

- "custom seed task"
- "domain-specific seed task"
- "SWE-bench-style/inspired task"
- "not yet imported from SWE-bench or Terminal-Bench"

This matters because the user wants reliable quantitative results. Inflating task provenance would make reports look more scientific than the evidence supports.

## Manifest Schema

Every current task now carries these top-level fields:

- `difficulty`: `easy`, `medium`, `hard`, or `expert`.
- `difficulty_rationale`: why that tier is appropriate; it must not be inferred from an agent's score.
- `provenance.type`: `custom_seed`, `domain_seed`, `inspired_by_external`, or `external_imported`.

The `agent-benchmark catalog` command exposes this data to humans and automation. Validation rejects invalid tiers and rejects imported tasks that omit reproducibility metadata.

## Minimum Metadata For Future Imported Tasks

When external benchmark importers are added, each imported task must record these fields inside `provenance`:

- `source_benchmark`: for example `SWE-bench`, `Terminal-Bench`, `WebArena`, or `OSWorld`.
- `source_id`: the upstream task or issue identifier.
- `source_url`: the canonical upstream URL when public.
- `source_version`: dataset release, commit SHA, or snapshot date.
- `license_note`: short note confirming the task can be redistributed or how it was transformed.
- `importer_version`: local importer version or commit.
- `type`: `external_imported`.

For custom seed tasks, use `provenance.type: custom_seed`, `domain_seed`, or `inspired_by_external` plus a project source description.

## Approved Authoritative Sources

`config/authoritative_corpora.json` records approved upstream benchmark contracts. It currently names SWE-bench Verified and Terminal-Bench Core, their official repositories, dataset/version labels, and evaluator entrypoints. Registry membership is a plan, not provenance: only a task with preserved upstream instance metadata and evaluator output may use `external_imported`.

`agent-benchmark preflight-authoritative` verifies that the registry is structurally valid and checks its Docker and upstream-tool prerequisites. A ready preflight is still only permission to begin a controlled import; it never changes a task's provenance.

`config/authoritative_pilots.json` may freeze an upstream selection before any agent sees the task. The SWE-bench freezer validates each selected instance's upstream difficulty and base commit, then saves a raw metadata snapshot plus SHA-256 under ignored `runs/`. Even this evidence is still `metadata_frozen_not_imported`: only an official evaluator result after a harness patch changes the evidence level.

## Next Iteration Recommendation

The metadata layer, selection gate, and source registry are now implemented. The next step is a real Docker-backed importer/evaluator bridge, not hand-labeling local tasks as external.
