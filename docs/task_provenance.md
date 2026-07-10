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

## Minimum Metadata For Future Imported Tasks

When external benchmark importers are added, each imported task should record:

- `source_benchmark`: for example `SWE-bench`, `Terminal-Bench`, `WebArena`, or `OSWorld`.
- `source_id`: the upstream task or issue identifier.
- `source_url`: the canonical upstream URL when public.
- `source_version`: dataset release, commit SHA, or snapshot date.
- `license_note`: short note confirming the task can be redistributed or how it was transformed.
- `importer_version`: local importer version or commit.
- `difficulty`: one of `easy`, `medium`, `hard`, `expert`, or a benchmark-native difficulty label.
- `provenance_type`: `external_imported`.

For custom seed tasks, use `provenance_type: custom_seed`, `domain_seed`, or `inspired_by_external`.

## Next Iteration Recommendation

Add non-failing validation warnings for task manifests that omit provenance metadata, then gradually annotate all current tasks. After that, build real importers instead of hand-labeling tasks as external.
