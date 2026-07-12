# Agent Benchmark Lab 用户手册

本项目是个人长期维护的 coding-agent 基准实验室。它回答的不是“哪个模型总分最高”，而是：

```text
harness x model x task x environment x budget profile -> 可追溯证据与多维分数
```

例如：同一默认模型下 Codex、Claude Code、opencode、Aider、Grok 哪个更适合你的工作方式；或同一 harness 在明确验证模型身份后，DeepSeek、mimo、LongCat、GPT、Gemini 等模型哪个更强。

本手册面向唯一使用者，说明当前可做什么、结果意味着什么、哪些地方仍不能下结论。实施和审计依据见 `docs/benchmark_readiness_audit.md`。

## 1. 当前快照

截至 2026-07-12，题库目录有 **31 条记录**：

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
| `cost_efficiency` | 4% | CLI 真正输出的 token/cost；缺失时为 0，不会拿工具数冒充成本。 |

必须同时看三组指标：

1. **strict total**：未测维度按 0，防止缺证据却虚高。
2. **verified coverage**：总权重中有确定性/结构化证据的比例。
3. **verified normalized score**：只在已验证维度上的归一化表现。

不要把 strict total 低直接理解为 agent 失败，也不要只看 normalized score 而忽略 coverage。跨 harness 排名还会使用共同有证据的 `comparable score`，避免一个 CLI 恰好输出 token 而另一个 CLI 不输出时造成不公平。

## 4. 模型身份与比较模式

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

## 5. 从零开始的个人工作流

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

## 6. Codex 与 Aider adapter 细节

| Adapter | 默认非交互命令 | 模型行为 | 遥测边界 |
| --- | --- | --- | --- |
| `codex` | `codex exec --json --ephemeral --sandbox workspace-write --skip-git-repo-check` | `unspecified` 用 Codex 当前默认；显式模型加 `-m`。 | JSONL 中的 command/file-change/usage 会被解析；缺失字段不补造。 |
| `aider` | `aider --yes-always --no-git --no-auto-commits --no-stream --message-file` | `unspecified` 用 Aider 当前配置；显式模型加 `--model`。 | 仅解析 Aider 明确输出的模型、token、cost；无工具 trace 时不假装有完整工具遥测。 |

两者都运行在每次复制的 task workspace。默认不在用户项目仓库内自动 commit。若你有特殊 provider、代理、模型别名或安全模式，可设置 `AGENT_BENCH_CODEX_COMMAND` 或 `AGENT_BENCH_AIDER_COMMAND` 覆盖模板；覆盖后先跑 `doctor` 和单题 smoke。

## 7. 外部权威轨道

SWE-bench 和 Terminal-Bench 不是本地普通题。它们必须通过官方 evaluator bridge：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-authoritative
PYTHONPATH=src python3 -m agent_benchmark.cli.main swebench-bridge \
  --instance-id <pilot-id> --adapter <adapter>
PYTHONPATH=src python3 -m agent_benchmark.cli.main terminal-bench-bridge \
  --instance-id <pilot-id> --adapter <supported-official-agent>
```

默认只展示计划；只有 `--execute` 才会调用真实 harness、Docker 和官方 evaluator。`resolved` 与 `not_resolved` 才是 scoreable；`evaluator_error` 是环境/评测错误，绝不能算作模型失败。外部轨道的含义、环境和任务分布不同，除非报告明确写出合并规则，否则不要与本地题直接平均。

## 8. 新增任务或新 CLI 的规则

新增 task 至少需要：明确 instruction、difficulty 与 rationale、provenance、公开/隐藏测试、protected paths、基线失败、参考解通过。新增 CLI 需要：非交互命令、模型选择行为、超时环境变量、解析能力边界、doctor 检查、单元测试和一次真实 smoke。

请勿把 `config/harnesses.example.json` 当成已启用配置。把它复制成被 gitignore 的 `config/harnesses.json`，或设置 `AGENT_BENCH_HARNESSES_FILE`，才会注册一个自定义 headless CLI。

## 9. 何时可以相信结果

可以相信“某一 run 的测试有没有通过”和“某一保存配置在这套题上的证据是什么”。暂时不能把单次 run、不同默认模型、低 coverage 的 strict total 或 evaluator 失败解释为普遍能力结论。

对个人工具选择，最低建议是：至少 3 个可比较 agent/model 配置、每个配置 3 次、同一固定 task cohort、完整保留模型身份/版本/预算/环境；再看均值、方差、任务级 95% CI、各领域轴和失败样本。对外部或“权威”结论，还必须完成 `docs/benchmark_readiness_audit.md` 中的高优先级缺口。
