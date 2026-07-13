# Agent Benchmark Lab 用户手册

本项目是个人长期维护的 coding-agent 基准实验室。它回答的不是“哪个模型总分最高”，而是：

```text
harness x model x task x environment x budget profile -> 可追溯证据与多维分数
```

例如：同一默认模型下 Codex、Claude Code、opencode、Aider、Grok 哪个更适合你的工作方式；或同一 harness 在明确验证模型身份后，DeepSeek、mimo、LongCat、GPT、Gemini 等模型哪个更强。

本手册面向唯一使用者，说明当前可做什么、结果意味着什么、哪些地方仍不能下结论。实施和审计依据见 `docs/benchmark_readiness_audit.md`。

## 1. 当前快照

截至 2026-07-12，题库目录有 **31 条记录**、**13 个 suite**：

| 类别 | 数量 | 含义 |
| --- | ---: | --- |
| 本地可运行题 | 26 | 项目自有或领域题，使用本地/容器 evaluator。 |
| `external_frozen` 记录 | 5 | 仅冻结的 SWE-bench 元数据，不能被普通 runner 伪装成已导入题。 |
| 基线失败且参考解通过 | 21 | 已通过最基本的“题目有对比度”质量门。 |
| 容器题库质量门待补 | 5 | 依赖第三方包，当前 `audit-corpus` 不会在 Docker 中复跑基线/参考解。 |

声明难度分布为 easy 7、medium 11、hard 9、expert 4。这个难度是题目作者的假设，不是已经测出的事实；只有来自多个真实 agent 配置、每个配置多次重复的结果，才能把题目认定为有区分度。

目前可用的内置 adapter：`aider`、`claude-code`、`codex`、`grok`、`opencode`，以及用于框架测试的 `dummy`、`generic-command`。`list-adapters` 只显示内置 adapter 或你显式配置的本地 registry；示例文件不会假装某个 CLI 已安装。

## 2. 题库与套件

任务并非全都应该混成一个平均分。每题都有难度、来源、领域、运行环境、公开/隐藏测试和 benchmark role。

| 套件 | 用途 | 建议场景 |
| --- | --- | --- |
| `real-smoke` | 一个简单连通性题 | 先确认某 CLI 能编辑、测试、保存 evidence。不可用于排名。 |
| `personal-probe` | 个人低成本样本 | 首次比较多个当前默认配置。 |
| `calibration` | easy 到 expert 的本地校准 | 三重复的基本比较。 |
| `hard-discrimination` | 偏 hard/expert 的本地筛选题 | 需要更高区分度时的主力套件。 |
| `optics-discrimination` | 光学由易到难梯子 | 光学/科学计算专门比较。 |
| `selection-ladder` | expert 到 easy 的完整筛选梯子 | 长预算、研究性跑分。 |
| `advanced` | 复杂工程题 | 定向压力测试。 |
| `process` / `test-writing` | 过程与测试生成能力 | 单能力诊断，不单独代表总能力。 |
| `swebench-pilot` | 官方 SWE-bench bridge 入口 | 独立外部轨道。 |
| `unified-hard` | 本地 hard 题与已 scoreable 的官方项 | 仅在报告明确来源、权重和排除项时使用。 |
| `comprehensive-screening-v1` | 固定的本地难易梯子 + SWE-bench Verified cohort | 一键完整筛选；本地与官方结果分轨报告。 |

本地题覆盖 Python、C、并发/内存管理、嵌入式协议、Web/视觉、CI、安全审查、全栈、数据管线，以及光学（薄透镜、Snell、干涉、PSF/FWHM、高斯光束、ABCD、成像管线）。题目与答案分离：agent 看到的只是 run workspace；`solution/` 不复制给 agent；隐藏测试在评分阶段才使用。

## 3. 评分体系

每个 task run 都保存 `result.json`、`trace.jsonl`、`stdout.log`、`stderr.log`、`diff.patch`、公开/隐藏测试结果和环境证据。默认严格总分是以下十项的加权和：

| 维度 | 权重 | 可接受的主要证据 |
| --- | ---: | --- |
| `task_completion` | 30% | 公开与隐藏验收命令。 |
| `execution_quality` | 12% | 题目声明的文件修改/质量检查。 |
| `intent_understanding` | 10% | 题目声明的目标文件与指令匹配检查。 |
| `self_repair` | 10% | 日志中的重试/修复模式；当前是 heuristic。 |
| `planning` | 8% | 题目要求的 `.agent-benchmark/plan.md` 等可验证产物。 |
| `test_discipline` | 10% | agent 新增测试的数量、断言和质量检查。 |
| `tool_use` | 6% | CLI 的结构化工具事件为 verified；仅由 workspace diff 推断的编辑为 heuristic。 |
| `visual_verification` | 4% | 静态 HTML、Playwright 可见性、截图像素证据。 |
| `safety_boundary` | 6% | protected path 的 SHA-256 完整性。 |
| `cost_efficiency` | 4% | 始终保存 CLI 真正输出的 token/cost；只有题目在运行前声明 `metadata.cost_budget_usd` 时才换算成该维度分。没有预算时成本只作独立观测，不使用任意美元换分。 |

必须同时看三组指标：

1. **strict total**：未测维度按 0，防止缺证据却虚高。
2. **verified coverage**：总权重中有确定性/结构化证据的比例。
3. **verified normalized score**：只在已验证维度上的归一化表现。

`instruction_match` 这类“改到了预期文件”的 intent 代理指标会显示在 strict total 中，但证据状态是 heuristic；它不能证明语义理解。没有任务级成本预算时，cost/token 会出现在 run 原始记录和 summary 中，却不会抬高 verified coverage 或制造效率分。跨 harness 排名还会使用共同有证据的 `comparable score`，避免一个 CLI 恰好输出 token 而另一个 CLI 不输出时造成不公平。

## 4. 重复次数、均值、方差与置信区间

一次 run 只是一条样本，不是能力结论。每个本地 task 的 `summary.json` 和 suite 报告会记录：

| 字段 | 计算方式 | 如何解释 |
| --- | --- | --- |
| `mean_score` | 多次严格分的算术均值 | 仅在同一固定 task cohort 内比较；不能脱离 coverage 单独看。 |
| `variance` / `stdev` | 同一 task、同一 adapter/model/profile 的重复结果 | 反映运行稳定性；0 也可能只是题太容易。 |
| `best_score` / `worst_score` | 重复中的极值 | 用于查看偶发成功/失败，不能代替均值。 |
| `score_confidence_interval_95` | 2-30 次重复使用双侧 Student-t 95% CI；单次为 unavailable | CI 重叠不自动证明相同，但不重叠值得进一步检查。 |
| `mean_duration_seconds` | agent 与评分阶段的时长均值 | 结合超时、Docker cache 与 evaluator 看。 |
| `mean_cost_usd` | 仅来自 CLI 明确输出的成本 | 缺失不是免费；不会用工具数替代。 |

标准比较最低使用 **3 次重复**。筛选门要求至少 3 个已识别配置、每个 3 次，即至少 9 条 eligible run，才可能将题目列为 `selection_ready_local_seed`。

官方 SWE-bench 也遵从 repetitions：每个 repetition 生成独立 bridge/harness patch，再由官方 evaluator 评分。报告给出 ranking candidate 的 `resolution_rate_percent`、scoreable attempt 数、resolved attempt 数、方差和 CI。`evaluator_error` 不会记为未解决，也不进入 rate 分母；diagnostic tail 只展示，不进入 official ranking rate。

## 5. 一键完整筛选卷

先在不花模型额度的情况下检查完整卷：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite comprehensive-screening-v1 \
  --adapters claude-code --models unspecified \
  --budget-profiles stress --repetitions 3
```

然后，下面**一条执行命令**覆盖固定的项目自有题与权威 SWE-bench Verified 题：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite comprehensive-screening-v1 \
  --adapter claude-code \
  --model unspecified \
  --budget-profile stress \
  --repetitions 3 \
  --label comprehensive-v1
```

它固定运行 11 道本地题（expert/hard/medium/easy）+ 9 道 SWE-bench Verified hard ranking candidate + 1 道 easy diagnostic tail。完整的本地 cohort 依次为：

| 层级 | 固定本地题 | 主要区分信号 |
| --- | --- | --- |
| expert | `c-systems-programming`、`systems-concurrency` | C 系统设计、并发正确性、内存/边界。 |
| hard | `embedded-protocol-parser`、`python-swebench-style`、`optics-abcd`、`optics-gaussian-beam`、`optics-psf-peak` | 复杂状态机、跨模块 bugfix、嵌入式与光学科学计算。 |
| medium | `code-review`、`frontend-visual`、`process-planning` | 安全审查、视觉/隐藏验收、显式计划与验证。 |
| easy diagnostic | `optics-thin-lens` | 低门槛诊断，不应单独决定排名。 |

官方 cohort 固定为 `config/authoritative_pilots.json` 的 `swe-bench-verified-hard-v2`：三个 `>4 hours` 候选、六个 `1-4 hours` 候选，最后一个 `<15 min` 的 Flask diagnostic tail。选择列表、上游 base commit 和角色均写入 task fingerprint；任意变更都会阻止错误恢复。每个权威题也会按 repetition 独立生成 patch，所以这是长且昂贵的实验；中断后从命令输出复制 `suite_run_dir`，再运行：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite \
  --suite-run-dir runs/<suite-run-id>
```

已保存的 task summary 不会重跑。若中断发生在一个 SWE bridge 内部，bridge 目录保留 patch 和 evaluator 状态；恢复 suite 时会复用该已完成 task summary，单个 bridge 的故障信息会被完整保留。

输出有两条主结论，**没有综合万能总分**：

1. **Local scorecard**：本地十维、coverage、verified normalized、领域轴、均值、方差和 CI。
2. **Official SWE resolution track**：只报告权威 evaluator 的 resolved/scorable/rate。它不被换算成伪造的 planning、intent、execution 或安全分，也不混入本地 strict average。

Terminal-Bench 是另一种终端环境任务，仍通过 `terminal-bench-bridge` 单独执行和报告。严肃比较不能把不同 evaluator 的任务混成一个万能总分。

### 完整卷如何计分

本地部分的 `mean_score` 是 11 道本地 comparative task 的等权平均；每题先在其 repetitions 内取均值。它不是官方题的折算分，也不把 diagnostic/smoke 题静默加权。官方部分的 `resolution_rate_percent` 是九道 ranking candidate 的 scoreable attempt 中，官方 evaluator 返回 `resolved` 的比例；任何 `evaluator_error` 都不进分子或分母。第十道 diagnostic tail 只展示，不进入该 rate。

因此可回答两个不同问题：本地分用于观察“计划、验证、视觉、嵌入式/光学等可测维度的工作方式”；SWE resolution 用于观察“这个固定权威 issue cohort 的端到端修复率”。两者都重要，但不能伪装成同一个量纲。

### 决策指数：给选工具用，不伪装成客观总分

完整卷额外计算 `balanced-v1` 决策指数，默认公式为：

```text
Decision Index = 55% x local verified-normalized score
               + 45% x official SWE resolution rate
```

55% 留给本地多领域 cohort，因为它覆盖你明确关心的计划、视觉、嵌入式和光学；45% 留给官方 issue 修复，因为它更接近真实大型仓库工程。SWE 不占过半，是因为它主要仍衡量 Python repository issue，不能代表你的全部目标领域。

指数的 profile、权重、配置 SHA-256 指纹、两个原始分量和 warnings 都写进 `suite_summary.json` 与 HTML/Markdown report。它只在以下条件满足时为 `ready`：每题至少三重复、本地 verified coverage 至少 60%、至少 9 个官方 ranking-candidate attempt 可被官方 evaluator 评分。缺少任何条件但两个分量仍存在时，仍会显示数值，但状态为 `provisional`；缺少任一分量时为 `unavailable`。不要仅凭这个指数决定胜负，仍应同时看两条原始轨道、领域轴、方差、CI 和失败样本。

决策指数**不会**改变本地 strict total，**不会**把官方题画进十维雷达图，也**不会**替代官方 resolution track。它的唯一作用是在固定 profile 下，把两个互补的结果以公开公式放到同一个选型视图中。profile 定义在 `config/decision_index_profiles.json`；任何调整必须在真实实验开始前冻结，并在报告中留下新的配置指纹。

### 不想拼命令时：极简启动器

先在仓库根目录安装一次短命令：

```bash
./benchmark install
```

之后，你可以新建一个本次实验专用目录，进入它，再执行：

```bash
mkdir -p ~/Documents/claude-benchmark-2026-07
cd ~/Documents/claude-benchmark-2026-07
agent-benchmark claude-code
```

它默认使用 `comprehensive-screening-v1`、`unspecified` 当前 CLI 默认模型、`stress`、三重复，并自动完成：环境 doctor、preflight、实际 suite run、dashboard 刷新和 macOS 浏览器打开。所有 task 证据、suite report、matrix/bridge artifacts 和 `dashboard/` 都放在**当前目录**，不会污染源码目录。想先用小一些的本地硬题检查流程：

```bash
agent-benchmark claude-code hard-discrimination
```

可用环境变量覆盖默认归档目录而不改变命令形状：

```bash
AGENT_BENCH_RESULTS_DIR="$HOME/Documents/MyBenchmarkResults" agent-benchmark opencode
```

底层 `run`、`run-suite`、`run-matrix` 和各自 resume 命令也会在成功完成后自动刷新 `<runs-dir>/dashboard/index.html`；启动器只是额外帮你自动打开它。

**当前边界：** 启动器会检查环境，但不会自动安装 Python/Node/Playwright 依赖、启动 Docker/Colima、完成 provider 登录，或替你处理需要确认的系统级操作。遇到 doctor/preflight 失败时，当前版本仍需要按提示修复。未来会补自动诊断与受控修复，并交付独立原生 macOS App；在那之前，不应把现有 CLI 流程理解为零配置产品。

## 6. 模型身份与比较模式

### 当前默认配置比较

最自然的日常问题是“我现在配置好的工具哪个更好用”。使用：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix \
  --suite personal-probe \
  --adapters codex,claude-code,opencode,aider,grok \
  --models unspecified --repetitions 3 \
  --label current-defaults
```

`unspecified` 让每个 CLI 使用自己的当前默认模型。结果是 **完整配置比较**，不是同模型比较。运行后要看 `model_identity`：`default_detected` 有观察到的身份，`default_unverified` 表示 CLI 没暴露身份。

### 同模型不同 harness 比较

只有所有 adapter 都能明确选择同一个模型、运行输出也证实为 `verified_match` 时，才能说“同模型下谁的 harness 更强”。使用本地、被忽略的 `config/model_registry.json` 做 adapter-specific 参数映射，再先运行 `preflight-matrix`。opencode 1.17.15 已知不能可靠使用 `--model`，所以它目前的显式同模型结论必须特别谨慎。

## 7. 从零开始的个人工作流

先检查本机而不花 token：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
PYTHONPATH=src python3 -m agent_benchmark.cli.main screening-report
```

先只验证一个新 adapter：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task python-bugfix --adapter codex --model unspecified --repetitions 1

PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task python-bugfix --adapter aider --model unspecified --repetitions 1
```

然后做三重复个人 probe：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite personal-probe --adapters codex,aider,claude-code,opencode,grok \
  --models unspecified --repetitions 3

PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix \
  --suite personal-probe --adapters codex,aider,claude-code,opencode,grok \
  --models unspecified --repetitions 3 --label current-defaults
```

这会消耗真实模型额度。首次只比较一个或两个 harness 更稳妥；需要高区分度时把 `personal-probe` 换为 `hard-discrimination`。中断后使用 `resume`、`resume-suite` 或 `resume-matrix`，不要重新花费已保存 repetition 的额度。

生成浏览结果：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
open runs/dashboard/index.html
```

每次比较后读取每个 suite 目录里的 `suite_summary.json`、`suite_report.md`、`suite_report.html`，并保留 run 目录作为证据。

## 8. Codex 与 Aider adapter 细节

| Adapter | 默认非交互命令 | 模型行为 | 遥测边界 |
| --- | --- | --- | --- |
| `codex` | `codex exec --json --ephemeral --sandbox workspace-write --skip-git-repo-check` | `unspecified` 用 Codex 当前默认；显式模型加 `-m`。 | JSONL 中的 command/file-change/usage 会被解析；缺失字段不补造。 |
| `aider` | `aider --yes-always --no-git --no-auto-commits --no-stream --message-file` | `unspecified` 用 Aider 当前配置；显式模型加 `--model`。 | 仅解析 Aider 明确输出的模型、token、cost；无工具 trace 时不假装有完整工具遥测。 |

两者都运行在每次复制的 task workspace。默认不在用户项目仓库内自动 commit。若你有特殊 provider、代理、模型别名或安全模式，可设置 `AGENT_BENCH_CODEX_COMMAND` 或 `AGENT_BENCH_AIDER_COMMAND` 覆盖模板；覆盖后先跑 `doctor` 和单题 smoke。

## 9. 外部权威轨道

SWE-bench 和 Terminal-Bench 不是本地普通题。它们必须通过官方 evaluator bridge：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-authoritative
PYTHONPATH=src python3 -m agent_benchmark.cli.main swebench-bridge \
  --instance-id <pilot-id> --adapter <adapter>
PYTHONPATH=src python3 -m agent_benchmark.cli.main terminal-bench-bridge \
  --instance-id <pilot-id> --adapter <supported-official-agent>
```

默认只展示计划；只有 `--execute` 才会调用真实 harness、Docker 和官方 evaluator。`resolved` 与 `not_resolved` 才是 scoreable；`evaluator_error` 是环境/评测错误，绝不能算作模型失败。外部轨道的含义、环境和任务分布不同，除非报告明确写出合并规则，否则不要与本地题直接平均。

## 10. 新增任务或新 CLI 的规则

新增 task 至少需要：明确 instruction、difficulty 与 rationale、provenance、公开/隐藏测试、protected paths、基线失败、参考解通过。新增 CLI 需要：非交互命令、模型选择行为、超时环境变量、解析能力边界、doctor 检查、单元测试和一次真实 smoke。

请勿把 `config/harnesses.example.json` 当成已启用配置。把它复制成被 gitignore 的 `config/harnesses.json`，或设置 `AGENT_BENCH_HARNESSES_FILE`，才会注册一个自定义 headless CLI。

## 11. 已执行的 Claude Code 抽样审计

2026-07-12 用 `claude-code --model unspecified --budget-profile stress --repetitions 1` 做了三个非 smoke 抽样。Claude 输出中观测到的默认模型为 `LongCat-2.0[1m]`；它们不是 harness 胜负结论，只用于验证题目合同、评分器和报告是否诚实。

| Task | 可重复运行目录 | 可验证结果 | 评分审计结论 |
| --- | --- | --- | --- |
| `process-planning` | `runs/20260712T155643Z-f0747e58` | 公开/隐藏测试均通过，计划产物包含 Inspect/Implement/Verify。 | 发现原检查对英文标题大小写过严，已改为 case-insensitive；修复后 planning=100 合理。 |
| `frontend-visual` | `runs/20260712T155828Z-109366b7` | 公开测试通过、隐藏视觉验收失败；页面仍为 `Status Page`，未满足 `System Status`。 | `task_completion=50`、视觉证据 3/4 通过是合理的部分失败，不允许因“改了文件”给满任务完成。 |
| `embedded-protocol-parser` | `runs/20260712T160819Z-e4111c01` | 公开 8/8、隐藏 22/22 通过；计划文件与 protected path 检查通过。 | strict=65.25；`execution_quality=50` 来自实际 `max_nesting_depth=7` 超过题目上限 5，故没有虚报满分。 |

这次审计还修正了三类会虚高或误导的证据：workspace diff 和 Claude `num_turns` 不再被当作 verified tool telemetry；只改预期文件的 `instruction_match` 降为 heuristic intent；无题目预算时美元/token 不再用任意系数换成成本分。旧 run 保存的是历史证据，评分规则变更后不要把旧 coverage 当作当前可比结论。

## 12. 何时可以相信结果

可以相信“某一 run 的测试有没有通过”和“某一保存配置在这套题上的证据是什么”。暂时不能把单次 run、不同默认模型、低 coverage 的 strict total 或 evaluator 失败解释为普遍能力结论。

对个人工具选择，最低建议是：至少 3 个可比较 agent/model 配置、每个配置 3 次、同一固定 task cohort、完整保留模型身份/版本/预算/环境；再看均值、方差、任务级 95% CI、各领域轴和失败样本。对外部或“权威”结论，还必须完成 `docs/benchmark_readiness_audit.md` 中的高优先级缺口。
