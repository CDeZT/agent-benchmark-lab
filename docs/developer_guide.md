# Agent Benchmark Lab 开发者手册

这份手册面向维护本仓库的人、未来的 coding agent，以及希望加入任务、adapter、评分器或权威题库轨道的贡献者。它描述的是当前实现边界，而不是愿景清单。

先阅读：

1. `README.md`：项目目标和用户入口。
2. `docs/user_guide.md`：用户实际会如何运行系统和解释结果。
3. `docs/benchmark_readiness_audit.md`：不能越过的科学结论边界。
4. `docs/handoff.md`、`docs/next_agent_prompt.md`：当前进展、交接要求和历史风险。
5. `docs/requirements.md`、`docs/conversation_requirements.md`：长期需求，包括嵌入式、光学、难易梯子、权威题库与避免假打分。

## 1. 项目目标与非目标

系统的最小可比较单位是：

```text
adapter/harness + observed model identity + fixed task contract
+ environment + budget profile + repetition
```

它既支持“当前 CLI 默认配置谁更适合我”，也预留“同模型不同 harness”的严格实验。默认 `--models unspecified` 是前者；它绝不能被写成同模型结论。后者必须使用 canonical model、adapter-specific 参数映射，以及运行后 `model_identity.status=verified_match`。

不要实现以下捷径：

- 不要将 CLI 参数、registry 名称或旧日志当作已验证模型身份。
- 不要因为任务最终通过，就补满 planning、intent、execution、safety、self-repair 或 tool-use 分。
- 不要将自建题、题目灵感或冻结元数据称为“导入的权威题”。
- 不要将本地任务、SWE-bench、Terminal-Bench、Web/GUI evaluator 直接平均成一个所谓全球总分。
- 不要为缺失的成本、工具、子代理或视觉证据捏造代理分数。

## 2. 目录与职责

| 路径 | 职责 |
| --- | --- |
| `src/agent_benchmark/cli/main.py` | CLI 参数、task/suite/matrix 生命周期和恢复入口。 |
| `src/agent_benchmark/runner/` | isolated workspace、adapter 执行、Docker evaluator、profile、汇总。 |
| `src/agent_benchmark/adapters/` | 内置 harness adapter；只负责调用和输出，不负责打分。 |
| `src/agent_benchmark/parsers/` | 从原始 CLI 输出中保守提取模型、token、cost、结构化工具事件。 |
| `src/agent_benchmark/scorers/` | 测试、完整性、过程、视觉和 evidence-status 评分。 |
| `src/agent_benchmark/reports/` | JSON、Markdown、HTML、雷达图和 matrix 展示。 |
| `src/agent_benchmark/unified_external.py` | 将官方 SWE bridge 结果接入 suite 的独立 resolution track。 |
| `benchmarks/tasks/<id>/` | 一个本地任务的 manifest、workspace、solution、hidden 测试。 |
| `benchmarks/suites/` | 固定 task cohort；suite 是比较合同，不是随手列表。 |
| `config/authoritative_*.json` | 权威题库 registry 和冻结 pilot 的 commit/难度/角色。 |
| `tests/test_framework.py` | 端到端框架、评分边界、统计和回归测试。 |
| `runs/` | 忽略的实验原始证据，绝不作为源码提交。 |
| `docs/` | 用户、评分、架构、交接、审计与研究性说明。 |

核心数据流：

```text
TaskSpec + ExperimentConfig
  -> Adapter -> isolated workspace -> saved raw evidence
  -> deterministic scorer -> task summary
  -> suite/matrix aggregation -> Markdown/HTML/JSON report
```

详见 `docs/architecture.md`、`docs/run_log_schema.md` 和 `docs/adapter_contract.md`。

## 3. 本地开发环境与最低自检

首次环境：

```bash
python3 -m pip install -r requirements-browser.txt
npm ci
npx playwright install chromium
```

开发前与每次有意义修改后至少运行：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
git diff --check
```

`audit` 会验证 manifest、题库质量、权威 registry、所有单测、`compileall` 和 foundation smoke suite。它默认不调用真实 provider；真实 adapter smoke 只有显式 `audit --include-real-harness` 才会消耗额度。

开始权威题或矩阵前使用：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-authoritative
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite <suite> --adapters <a,b> --models unspecified --repetitions 3
```

## 4. Task 合同

每个本地 task 位于 `benchmarks/tasks/<task-id>/`。任务 manifest 是实验合同；改动 instruction、测试、protected path、solution 或评分检查后，task fingerprint 会变化，旧结果不能继续用于难度校准、排名或 resume。

一个可比较任务至少需要：

- 唯一 `id`、明确 `title`、具体可执行 `instruction`。
- `difficulty`（easy/medium/hard/expert）与解释；这是先验假设，不是经验事实。
- `provenance`：明确 `custom_seed`、`domain_seed` 或合规的外部来源。
- `workspace/`：agent 唯一可见的初始工作目录。
- `solution/`：仅供 baseline/reference 审计和维护者验证，绝不复制给 agent。
- 公开 `test_command`、私有 `hidden_test_command`、`protected_paths`。
- `process_checks`、`visual_checks` 或其他能产生可保存证据的任务特定检查。
- baseline 必须失败、reference 必须通过；使用 `audit-corpus` 验证。

不要只因“题目看起来复杂”就放进 ranking cohort。新题的正确生命周期是：

1. 编写 workspace、solution、public/hidden tests 和 manifest。
2. `validate` + dummy/reference + `audit-corpus`。
3. 先作为 `smoke_only` 或 `awaiting_real_evidence` 积累真实多配置样本。
4. 用 `calibrate-difficulty` 和 `screening-report` 判断是否具备区分度。
5. 只有满足门槛才进入 comparative cohort；过易、过难或无差异题 retune/replace。

容器依赖题必须声明 `metadata.environment=container_required` 与依赖/资源设置；不得在 host 缺包时静默跳过然后算成功。

## 5. Suite、完整卷与外部题

suite 是一组**固定、可审计**的 task contract。不要在同一次已开始的矩阵里修改 suite 列表；resume 会拒绝 fingerprint 不一致。

`comprehensive-screening-v1` 是当前用户级完整卷：

- 本地：11 道 expert -> hard -> medium -> easy comparative task。
- 官方：9 道 SWE-bench Verified ranking candidate，另加 1 道 diagnostic tail。
- 本地与官方共用恢复、目录与证据生命周期，却不共用评分量纲。

本地 suite mean 只汇总本地 `comparative_candidate`；官方 resolution rate 只以 ranking candidate 的可评分 attempts 计算。`evaluator_error` 不进分母，diagnostic tail 不进 rate。报告不得把官方 30% task-completion 占位、官方任务或 tail 混入本地 scorecard、雷达图、领域轴、comparable score 或 global mean。

`config/decision_index_profiles.json` 的 `balanced-v1` 是单独的个人决策辅助层：55% local verified-normalized + 45% official SWE resolution。它必须保存 profile 内容和 SHA-256 指纹，并满足 repetition、local coverage、official scorable attempts 的门槛才标为 `ready`。不满足门槛最多为 `provisional`；它绝不是 local/global evaluator total。新增 profile 必须说明应用场景、权重理由、门槛、版本号，并补回归测试。

Terminal-Bench、WebArena、OSWorld 等应保持新 evaluator track，除非先定义、冻结并验证跨 evaluator 的统计模型。参考 `docs/corpus_strategy.md`。

## 6. 评分与证据状态

默认严格维度权重是：completion 30、intent 10、planning 8、execution 12、self-repair 10、test discipline 10、tool use 6、visual 4、safety 6、cost 4。具体定义见 `docs/scoring.md`。

每个维度必须有三种状态之一：

| 状态 | 含义 | 如何使用 |
| --- | --- | --- |
| `verified` | 确定性测试、哈希、结构化 trace 或保存的 evaluator 直接证明。 | 可进入 verified coverage/normalized 和公平比较。 |
| `heuristic` | 有用但不构成因果证明的代理信号。 | 显示在 strict total，不能抬高 verified coverage。 |
| `unavailable` | 没有足够证据。 | 严格分中为 0；不补分。 |

重要边界：

- `instruction_match` 仅证明改到了预期文件，通常是 heuristic intent。
- workspace diff 仅是 heuristic tool-use fallback；Claude `num_turns` 也不是完整 tool trace。
- 结构化 Codex JSONL command/file events 等可作为 verified tool evidence，但 parser 必须保守。
- 公开/隐藏测试可证明 completion，不自动证明计划或安全。
- `self_repair` 当前主要是日志模式 heuristic；不要把关键词匹配升级为强结论。
- cost/token 永远保存为 raw evidence；只有运行前 task manifest 声明正数 `metadata.cost_budget_usd` 时，才可产生 verified `cost_efficiency` 分。禁止临时修改预算来迎合已知结果。

统计规则：单次不产生 CI；2-30 次任务重复使用双侧 Student-t 95% CI。标准比较最低三次。更高层矩阵不得凭空制造统计无意义的“全局 CI”。

## 7. 新增或修复 Adapter

adapter 的职责是让 harness 在 isolated workspace 中自然工作、保存命令/输出/时长，并返回保守解析后的 evidence；它不能识别 task id、直接复制 solution、改测试、自己打分或丢弃失败日志。

新增内置 adapter 的建议顺序：

1. 在 `src/agent_benchmark/adapters/` 创建实现，遵循 `docs/adapter_contract.md`。
2. 设计无交互 command template，支持 workspace、instruction file、prompt、model、timeout 和 profile 环境变量。
3. 在 registry 中显式注册，并让 `doctor` 检查二进制和必要 override 环境变量。
4. 在 `parsers/` 为可验证的模型/usage/tool telemetry 添加解析；无法确定就留空。MimoCode 的 JSONL 若只有 token/cost 而没有 `model`，必须保存前者且让模型身份保持 pending。Antigravity CLI (`agy --print`) 当前只返回人类可读响应；不能从其文本中提取模型、token、cost 或工具调用，也不应为了 identity probe 额外消耗一次推理。
5. 为 template、parser、doctor、超时和 evidence status 添加回归测试。
6. 先跑 `python-bugfix` 或 `real-smoke` 的一次真实 smoke；再进入 matrix。

未知 headless CLI 可用被 gitignore 的 `config/harnesses.json` 或 `AGENT_BENCH_HARNESSES_FILE` 显式注册。`config/harnesses.example.json` 只是一份示例，绝不应被自动注册为“已安装”。

## 8. 扩展 Scorer 或 Report

先问：新信号是否能证明现有维度，还是只是新日志？优先将证据附着在既有十维中，避免创建无法比较的分数面。

新增 scorer 的完成条件：

- 原始输入、阈值、命令、输出和判断保存在 run artifacts/trace 中。
- 失败、超时、无工具和无证据路径都有明确结果。
- 明确标注 verified、heuristic 或 unavailable。
- 至少有一个通过、失败、边界/缺失证据回归测试。
- 更新 `docs/scoring.md`、用户手册和 implementation status。

新增 report 字段时，Markdown、HTML、JSON 三种输出必须一致。权威外部字段先进入 official track，不得顺手混入 local radar。对 report 逻辑添加小型 synthetic summary 单元测试，避免只靠手工打开 HTML。

## 9. 运行产物、恢复与调试

task run 通常保存：`experiment_manifest.json`、`checkpoint.json`、每次 repetition 的 `instruction.txt`、`result.json`、`trace.jsonl`、stdout/stderr、diff、测试/视觉/环境证据，以及 `summary.json`/HTML/Markdown report。

每个完成的 CLI `run`、`run-suite`、`run-matrix` 及其 resume 入口都会自动重建 `<runs-dir>/dashboard/index.html`。不要把 dashboard 重建放进内部每道 task 的循环，否则完整矩阵会反复扫描历史 artifacts。Claude Code 的 `unspecified` 默认模型模式会先在临时目录执行一次禁工具、无持久 session、`$0.05` 硬上限的 JSON 身份探测，并将结果缓存到 `suite-*/model_probe.json`；OpenCode 的 `unspecified` 模式会创建一个隔离 JSON session、导出同一 session 获取实际 `info.model.id`，再删除这条 probe session。两者都是身份元数据，绝不能充当任务得分证据。Codex 的可读取 `config.toml` 默认模型只能作为 `configured` hint，绝不可升级为 observed identity。MimoCode 的 JSONL 默认输出可能不带模型字段，即使使用 `mimo` adapter 完成了 token/cost 解析，也不得让它显示为 observed model。Antigravity CLI 的 `agy --print` 默认模式没有可靠身份/遥测 schema，因此只保存原始 stdout/stderr，probe 状态为 unsupported，绝不为此额外发起模型调用。`SuiteProgress` 是运行时 UI 边界：runner 仅发送 task/repetition/adapter 事件和解析到的 `detected_model`，UI 只向 stderr 渲染并将 `suite-*/live_status.json` 原子写入；显示或写状态失败不得影响 agent 调用、评分或保存证据。`workspace.ready` 和 `environment.preparing` 是 UI 的真实上下文事件；UI 可以扫描当前隔离 workspace 的文件 mtime 并展示 mutation，但不得伪造成 harness 工具轨迹或思考过程。local task 的 `title` 应随 `task_started` 传入，用作主视觉文本；task id 保持为次级可审计标识。requested model、启动探测、configured hint 与任务输出 observed model 必须分别保存/显示，未观察到身份时不得用 CLI 标签填充。宽交互终端默认使用 Rich 管理的彩色 full-width alternate screen TUI：项目代码不得再手写 cursor move/clear ANSI 序列；Rich 负责 redraw 与恢复，80x24 是必须回归覆盖的下限。完成、失败或 Ctrl-C 路径必须恢复普通 screen。`plain`、`compact` 与 `TERM=dumb` 保持安全退化。ETA 只能来自已完成 attempt 的真实时长，样本为零时必须显示 unavailable/calculating。仓库根目录的 `./benchmark install` 会在 `~/.local/bin/agent-benchmark` 创建符号链接；用户随后在自己创建的结果目录中执行 `agent-benchmark claude-code`，当前目录就是 runs root。启动器执行 doctor/preflight/run/dashboard，最后调用 `open`。保持它只做编排，不复制 runner 或 scorer 逻辑。

suite 保存 `suite_manifest.json`、`task_summaries/`、checkpoint 和 suite reports；matrix 再保存每个组合的 summary 和 nested suite runs。

恢复命令：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume --experiment-dir runs/<experiment-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite --suite-run-dir runs/<suite-run-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-matrix --matrix-run-dir runs/<matrix-run-id>
```

不要删除 checkpoint 后伪装重跑为同一实验；不要绕过 task/suite fingerprint 拒绝。对 SWE bridge，保留同一个 bridge directory 以复用已生成 patch；没有明确意图不得为 evaluator 故障重新消耗一次 harness 调用。

## 10. 文档、状态与 Git 交接

每个有意义的阶段结束时，更新：

- `README.md`
- `docs/user_guide.md`
- `docs/developer_guide.md`（若开发工作流、目录或扩展合同改变）
- `docs/handoff.md`
- `docs/project_journal.md`
- `docs/implementation_status.md`
- `status/implementation_status.json`
- `docs/next_agent_prompt.md`

提交前运行自检、阅读 `git status`，只 stage 当前任务相关文件。保留用户或其他 agent 的无关改动；不使用 destructive git 操作。确认无误后 commit。`runs/`、本地 registry、provider 凭据和任何 token/日志证据不提交。

仓库代码采用 GPL-3.0；新增可分发的第三方源码、数据集、任务文本或资源前，必须核对其许可证是否允许再分发，并保留必要 notice。冻结的权威 benchmark metadata 与忽略的运行产物不能被误写成由本项目重新授权。

## 11. 当前下一阶段

最有价值的下一步不是增加更多表面功能：

1. 固定少量 hard/expert cohort，对至少三个可识别配置各跑三次。
2. 完成 Docker-backed corpus audit，使五个容器题真正通过 baseline/reference 门。
3. 以通过率、方差、CI 和失败模式校准题目，生成首批 `selection_ready_local_seed`。
4. 跑完整的 SWE-bench hard cohort，并保持 official resolution track；再独立完成至少一个 Terminal-Bench scoreable run。
5. 为自我修复、子代理、浏览器交互和成本预算补充因果、版本化证据，而不是给启发式规则加权。

完成这些前，系统可以作为严谨的个人实验工具，不能作为对外普适排行榜。
