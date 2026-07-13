# Agent Benchmark Lab

**English** | [简体中文](#简体中文)

An evidence-backed laboratory for evaluating real coding-agent combinations:

```text
harness x model x fixed task cohort x environment x budget profile
    -> raw evidence + multi-dimensional scores + uncertainty
```

## What It Is

Agent Benchmark Lab helps answer two different practical questions:

- **Current-configuration comparison:** Which of Claude Code, opencode, Codex, Aider, or another CLI works best with the model each tool is currently configured to use?
- **Strict same-model comparison:** Which harness is stronger only after every adapter can select, and its output verifies, the same model identity?

It is not a generic model leaderboard. It does not disguise outcomes from different evaluators as one universal score.

## Current Maturity

The project can run isolated tasks, public and hidden tests, protected-file integrity checks, real CLI adapters, repeated task/suite/matrix experiments, resumable runs, reports, and separate local versus official SWE-bench result tracks.

It cannot yet honestly claim that one harness is generally stronger than another. That requires at least three identified real configurations, three repetitions each, and empirical task-discrimination evidence from `screening-report`. The current selection-ready task count is intentionally zero.

`comprehensive-screening-v1` is the fixed full cohort:

- 11 local comparative tasks spanning expert to easy.
- 9 hard SWE-bench Verified ranking candidates.
- 1 diagnostic tail task, visible but excluded from official ranking rate.

It reports three complementary views:

1. **Local scorecard:** ten local dimensions, verified coverage, domain axes, mean, variance, and confidence intervals.
2. **Official SWE resolution track:** official `resolved / scorable attempts` and resolution rate.
3. **`balanced-v1` decision index:** 55% local verified-normalized score + 45% official SWE resolution rate. It is a transparent personal selection aid, not an objective benchmark total.

Official evaluator errors are not model failures. Official tasks never enter the local total, domain axes, radar charts, or matrix ranking.

## Documentation

| Audience | Document | Purpose |
| --- | --- | --- |
| Users | [User guide](docs/user_guide.md) | Setup, smoke runs, matrices, full cohort, statistics, recovery, and result interpretation. |
| Developers and future agents | [Developer guide](docs/developer_guide.md) | Architecture, task/adapter/scorer/report extensions, tests, recovery, and maintenance rules. |
| Result reviewers | [Benchmark readiness audit](docs/benchmark_readiness_audit.md) | Known scientific limits and the path to higher-confidence conclusions. |
| Maintainers | [Handoff](docs/handoff.md) and [next-agent prompt](docs/next_agent_prompt.md) | Current status, hard rules, and unfinished work. |
| Scoring readers | [Scoring specification](docs/scoring.md) and [capability taxonomy](docs/capability_taxonomy.md) | Weights, evidence status, statistics, and domain axes. |
| Corpus contributors | [Corpus strategy](docs/corpus_strategy.md) and [task provenance](docs/task_provenance.md) | Local tasks, SWE-bench, Terminal-Bench, and licensing boundaries. |

## Quick Start

Install browser-verification prerequisites once:

```bash
python3 -m pip install -r requirements-browser.txt
npm ci
npx playwright install chromium
```

Check the local environment without spending model tokens:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
```

Run a low-cost real-adapter smoke test:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task python-bugfix --adapter claude-code \
  --model unspecified --repetitions 1
```

`--model unspecified` means “use this CLI's current default model and record any observed identity.” It compares current full configurations, not a same-model harness experiment.

### One Friendly Command

On macOS, install the short command once from the repository:

```bash
./benchmark install
```

Then create a folder for one experiment, enter it, and run one short command:

```bash
mkdir -p ~/Documents/claude-benchmark-2026-07
cd ~/Documents/claude-benchmark-2026-07
agent-benchmark claude-code
```

It runs doctor and preflight, uses the fixed full cohort with three repetitions, writes every artifact into the **current directory**, refreshes `./dashboard/index.html`, and opens the dashboard when finished. Use `agent-benchmark opencode hard-discrimination` for a smaller local run. Override the destination explicitly with `AGENT_BENCH_RESULTS_DIR=/path/to/results`.

## Run The Full Fixed Cohort

Run the no-cost preflight first:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite comprehensive-screening-v1 \
  --adapters claude-code --models unspecified \
  --budget-profiles stress --repetitions 3
```

Then run the cohort:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite comprehensive-screening-v1 \
  --adapter claude-code --model unspecified \
  --budget-profile stress --repetitions 3 \
  --label comprehensive-v1
```

This can take a long time and consume real provider budget. Resume an interrupted suite from the directory printed by the command:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite \
  --suite-run-dir runs/<suite-run-id>
```

Reports are saved as `suite_report.html`, `suite_report.md`, and `suite_summary.json`. Build the historical dashboard with:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
open runs/dashboard/index.html
```

## Rules That Protect Result Quality

- Do not rank from one run, an unknown model identity, or low evidence coverage.
- Use a fixed cohort and at least three repetitions for serious comparisons; inspect means, variance, task-level 95% CI, failure samples, and domain axes.
- Read strict total, verified coverage, and verified-normalized score together.
- Tool-call count is not cost. Raw token/cost data is saved, but cost efficiency needs a task budget frozen before the experiment.
- `external_frozen` metadata is not an imported benchmark task. SWE-bench and Terminal-Bench must use their official bridges/evaluators.
- `runs/` contains ignored evidence artifacts. Do not commit model logs, patches, credentials, or sensitive outputs.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) (GPL-3.0). You may use, modify, and distribute it; when distributing a derivative work, provide corresponding source under GPL-3.0 and retain the required notices. The project is provided without warranty.

---

<a id="简体中文"></a>

# 简体中文

这是一个用来评估真实 coding-agent 组合的、保留完整证据的长期实验室：

```text
harness x model x 固定题目组 x 环境 x 预算档位
    -> 原始证据 + 多维分数 + 不确定性
```

## 它解决什么问题

项目区分两个实际问题：

- **当前配置比较**：此刻的 Claude Code、opencode、Codex、Aider 等 CLI 各自使用当前默认模型时，哪个更适合实际工作流？
- **严格同模型比较**：只有每个 adapter 都能选择同一个模型，且运行输出验证模型身份后，才比较 harness 本身。

它不是通用模型排行榜，也不会把不同 evaluator 的结果伪装成一个万能总分。

## 当前成熟度

当前版本已经能完成：隔离任务、公开/隐藏测试、受保护文件完整性检查、真实 CLI adapter、重复 task/suite/matrix 实验、中断恢复、报告，以及本地题与官方 SWE-bench 结果分轨。

但它还不能诚实地宣称“某个 harness 普遍更强”。要得到这样的结论，至少需要三个模型身份可识别的真实配置、每个配置三次重复，并通过 `screening-report` 证明题目确实具有区分度。当前 `selection_ready` 题数为 0，这是严谨状态提示，不是运行故障。

`comprehensive-screening-v1` 是固定完整卷：

- 11 道从 expert 到 easy 的本地比较题；
- 9 道 SWE-bench Verified 高难候选题；
- 1 道只展示、不进入官方排名率的诊断尾题。

它会给出三种互补结果：

1. **本地 scorecard**：本地十维、verified coverage、领域轴、均值、方差和置信区间。
2. **官方 SWE resolution track**：官方 evaluator 的 `resolved / scorable attempts` 与修复率。
3. **`balanced-v1` 决策指数**：55% 本地 verified-normalized 分 + 45% 官方 SWE 修复率。它是透明的个人选型辅助，不是客观 benchmark 总分。

官方 evaluator 错误不算模型失败；官方题不会进入本地总分、领域轴、雷达图或 matrix 排名。

## 文档入口

| 读者 | 文档 | 用途 |
| --- | --- | --- |
| 使用者 | [用户手册](docs/user_guide.md) | 环境配置、smoke、矩阵、完整卷、统计、恢复和结果解释。 |
| 开发者与下一位 agent | [开发者手册](docs/developer_guide.md) | 架构、Task/Adapter/Scorer/Report 扩展、测试、恢复与维护规则。 |
| 审查结果的人 | [基准就绪审计](docs/benchmark_readiness_audit.md) | 已知科学边界与提高可信度的路径。 |
| 维护者 | [交接文档](docs/handoff.md) 与 [下一 agent 提示词](docs/next_agent_prompt.md) | 当前状态、硬规则和未完成事项。 |
| 理解分数的人 | [评分规范](docs/scoring.md) 与 [能力分类](docs/capability_taxonomy.md) | 权重、证据状态、统计和领域轴。 |
| 题库贡献者 | [题库策略](docs/corpus_strategy.md) 与 [题目来源](docs/task_provenance.md) | 本地题、SWE-bench、Terminal-Bench 与许可证边界。 |

## 快速开始

首次使用浏览器视觉检查时安装依赖：

```bash
python3 -m pip install -r requirements-browser.txt
npm ci
npx playwright install chromium
```

先做不花模型额度的环境和项目检查：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
```

用真实 adapter 进行一次低成本 smoke：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task python-bugfix --adapter claude-code \
  --model unspecified --repetitions 1
```

`--model unspecified` 表示“使用该 CLI 此刻默认模型，并记录实际观察到的模型身份”。因此它比较的是当前完整配置，而不是同模型 harness 对决。

### 一条友好命令

在 macOS 上，先在仓库根目录安装一次短命令：

```bash
./benchmark install
```

之后新建本次实验的文件夹，进入它，只运行一条短命令：

```bash
mkdir -p ~/Documents/claude-benchmark-2026-07
cd ~/Documents/claude-benchmark-2026-07
agent-benchmark claude-code
```

它会自动执行 doctor 和 preflight，使用三重复的固定完整卷，把所有原始证据和结论写入**当前目录**，刷新 `./dashboard/index.html`，并在结束后自动打开看板。较小的本地实验可以用 `agent-benchmark opencode hard-discrimination`。使用 `AGENT_BENCH_RESULTS_DIR=/你的/结果目录` 可显式覆盖输出位置。

## 运行固定完整卷

先运行不花 token 的预检：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite comprehensive-screening-v1 \
  --adapters claude-code --models unspecified \
  --budget-profiles stress --repetitions 3
```

然后执行完整卷：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite comprehensive-screening-v1 \
  --adapter claude-code --model unspecified \
  --budget-profile stress --repetitions 3 \
  --label comprehensive-v1
```

它可能运行很久并消耗真实 provider 额度。中断后使用命令打印出的目录恢复：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite \
  --suite-run-dir runs/<suite-run-id>
```

报告在 `suite_report.html`、`suite_report.md` 和 `suite_summary.json`。生成历史看板：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
open runs/dashboard/index.html
```

## 保护结果质量的规则

- 不要根据单次 run、未知模型身份或低 evidence coverage 排名。
- 严肃比较使用固定题目组与至少三次重复；同时看均值、方差、任务级 95% CI、失败样本和领域轴。
- `strict total`、`verified coverage`、`verified-normalized score` 必须一起看。
- 工具调用数不是成本。原始 token/cost 会保存，但成本效率必须在实验前冻结任务级预算后才能计分。
- `external_frozen` 元数据不是已导入题；SWE-bench 与 Terminal-Bench 必须走官方 bridge/evaluator。
- `runs/` 保存被忽略的证据产物；不要提交模型日志、patch、凭据或敏感输出。

## 许可证

本项目使用 [GNU General Public License v3.0](LICENSE)（GPL-3.0）。你可以使用、修改和分发；发布基于本项目的衍生作品时，须按 GPL-3.0 提供相应源码并保留必要声明。项目按“现状”提供，不提供担保。
