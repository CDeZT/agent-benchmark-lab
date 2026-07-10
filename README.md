# Agent Benchmark Lab

Agent Benchmark Lab is a long-term benchmark project for measuring real coding-agent combinations:

```text
harness x model x task x environment x budget profile -> evidence-backed scores
```

The project is intentionally broader than a model leaderboard. It is designed to answer practical questions such as:

- Which harness is stronger when using the same model?
- Which model works best inside the same harness?
- Which harness/model pair best matches a user's real engineering workflow?
- How well does an agent understand intent, plan, use tools, test, inspect visuals, repair bugs, and continue autonomously?

## Current Status

当前仓库是一个可运行的早期 benchmark framework，不是已经完成的权威排行榜。当前有 **19 个任务定义**、5 个 suite、76 个 unittest 测试函数、审计命令和真实 harness smoke 路径。

已实现：
- 10 维度加权评分体系；所有非零分都必须来自可保存证据：
  - task_completion(30%) — 公开/隐藏测试执行结果
  - intent_understanding(10%) — agent 是否修改了正确的文件
  - planning(8%) — plan.md 文件存在且内容合格
  - execution_quality(12%) — agent 是否真的修改了源码
  - self_repair(10%) — stdout/stderr 中的自我修复模式
  - test_discipline(10%) — 测试文件质量和数量
  - tool_use(6%) — 工具调用多样性和数量
  - visual_verification(4%) — HTML 静态检查
  - safety_boundary(6%) — SHA-256 完整性检查
  - cost_efficiency(4%) — 仅使用真实 token/cost 数据；没有真实用量证据时为 0
- 19 个当前任务定义（bugfix/feature/refactor/test-writing/visual/embedded/optics/fullstack/data-pipeline/CI调试/代码审查/代码库理解/项目生成等）
- 当前任务是项目自定义 seed/inspired tasks，部分受 SWE-bench、Terminal-Bench 等思路启发；尚未真正导入权威外部题库。详见 `docs/task_provenance.md`。
- 4 种适配器（dummy/generic-command/opencode/claude-code）
- 真实 harness 输出解析（模型名、工具调用、token、cost）
- 矩阵运行（adapter × model × budget_profile）
- 公开测试 + 隐藏测试 + SHA-256 完整性检查
- 静态 HTML 视觉检查
- 过程检查（plan.md、文件变更、测试质量、指令匹配）
- Markdown + HTML 报告（含 SVG 雷达图）
- 自动计算均值、方差、标准差
- 一键审计、环境诊断、交接提示

See `docs/roadmap.md` and `docs/handoff.md` before extending the system.

## Quick Start

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-tasks
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit --include-real-harness
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
PYTHONPATH=src python3 -m agent_benchmark.cli.main run --task python-bugfix --adapter dummy --model smoke --budget-profile oneshot --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --model smoke --budget-profile open_ended --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite foundation --adapters dummy --models smoke-a,smoke-b --budget-profiles oneshot,open_ended --repetitions 1
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run outputs are written under `runs/` by default.

## Safety

API keys, provider credentials, and local harness configuration must be supplied through environment variables or local files excluded by `.gitignore`. This repository should never store secrets.

## Handoff

For context transfer to another agent, use:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
```

The source file is `docs/next_agent_prompt.md`.
