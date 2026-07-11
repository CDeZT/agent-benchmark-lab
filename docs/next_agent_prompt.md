# Next Agent Prompt

Copy this prompt into the next coding agent if this thread cannot continue.

```text
你现在接手 `/Users/wangzilin/Documents/agent_Benchmark`。

项目目标：
这是一个长期维护的个人 agent/harness/model 量化评测系统，不是普通模型排行榜。核心比较对象是：

    harness x model x task x environment x budget profile

用户最关心的问题包括：
- 同一个模型下，Claude Code 和 opencode 哪个 harness 更强。
- 同一个 harness 下，DeepSeek / mimo / longcat / GPT / Gemini 等模型哪个更适合。
- 完整 harness/model 组合在真实工程任务中的表现。
- 不只看最终 pass/fail，还要量化意图理解、计划、子任务/子代理、自测、视觉检查、自我修复、工具使用、成本、耗时、稳定性。

你必须先读这些文件：
- docs/handoff.md
- docs/implementation_status.md
- docs/requirements.md
- docs/conversation_requirements.md
- docs/project_journal.md
- docs/task_provenance.md
- docs/corpus_strategy.md
- docs/claude_code_handoff.md
- README.md

开始工作前先运行：

    PYTHONPATH=src python3 -m agent_benchmark.cli.main status
    PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
    PYTHONPATH=src python3 -m agent_benchmark.cli.main catalog
    PYTHONPATH=src python3 -m agent_benchmark.cli.main calibrate-difficulty
    PYTHONPATH=src python3 -m agent_benchmark.cli.main taxonomy
    PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
    PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
    PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix --suite calibration --adapters opencode,claude-code --models mimo-v2.5-pro --model-registry config/model_registry.example.json --repetitions 3
    PYTHONPATH=src python3 -m agent_benchmark.cli.main resume --help
    PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite --help
    PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-matrix --help
    PYTHONPATH=src python3 -m unittest discover -s tests -v

重要规则：
- 不要假打分。没有证据的维度保持 0 或 partial，不要为了好看填分。
- 报告严格总分时，必须同时报告 verified evidence coverage 和 verified normalized score；不要把未测维度导致的低严格分误读为任务失败。
- 不要把当前自定义 seed/inspired 任务说成已导入的权威题库；外部导入还没实现。
- 新任务必须声明 `difficulty`、`difficulty_rationale` 和 `provenance`；外部导入任务必须保留上游来源、版本、许可和 evaluator 证据。
- 依赖无法在当前环境复现的任务必须标记 `container_required`，不得混进默认本机比较或把跳过测试当作成功。
- `container_required` 任务已有 Docker evaluator v1；当前 Colima Docker daemon 可用，且已有 `python-fullstack` 容器运行证据。保留每次 run 的 `environment.Dockerfile`、`environment.json` 和 `environment-build.log` 作为环境证据。
- 同模型跨 harness 比较必须使用 canonical model + adapter-specific model registry；检查报告 `model_identity.status`，只有 `verified_match` 才能做同模型结论。不要把 CLI 参数标签当作模型身份事实。
- 在调用真实 harness 前先执行 `preflight-matrix`。如果它报告 registry identity hint mismatch，配置可以用于调试但不可用于公平排名；先修正映射，再花费 token。
- 当前 opencode 1.17.15 的 `--model` 会崩溃，adapter 只能使用其配置默认模型。即使 registry 写了 opencode 映射，也必须用运行输出验证实际模型，不能宣称该命令选中了某个模型。
- 矩阵的主排名是任务级共同证据维度的 comparable score；严格总分只作诊断。模型身份不是 `verified_match` 的行必须称为 provisional，不能写成同模型结论。
- `cost_efficiency` 只能来自真实 token/cost 数据；工具调用次数只能作为 `tool_use` 证据。
- 每次新增功能后，必须补测试或可验证命令。
- 每次迭代结束前必须运行自检，至少运行 `agent-benchmark audit`。
- 每次迭代如果改变需求状态，必须更新：
  - README.md
  - docs/handoff.md
  - docs/project_journal.md
  - docs/implementation_status.md
  - status/implementation_status.json
- 每次确认无错误后都要 commit。提交前检查 `git status`，只提交本任务相关文件。
- `runs/` 是运行产物目录，被 gitignore 忽略，不要提交。
- 真实 opencode/Claude Code 运行可能产生 token 成本。只有在用户允许或明确需要时才跑真实 harness；普通 audit 默认不跑真实 harness。
- 如果跑真实 harness，优先用低成本 `real-smoke` suite。

当前已实现的大方向：
- CLI benchmark lab。
- task/suite/matrix runner（当前 19 个任务定义，6 个套件，`calibration` 覆盖 easy 到 expert）。
- public tests + hidden tests。
- SHA-256 protected path integrity。
- static HTML visual checks。
- process planning evidence checks。
- 10 维度评分体系；所有非零分都必须有真实执行证据。
- dummy/generic/opencode/claude-code adapters。
- 真实 harness 输出解析（模型名、工具调用、token、cost），并把 token/cost 汇总进 summary。
- doctor/status/audit 命令。
- real opencode/Claude Code smoke 已经在 python-bugfix 上通过。
- 109 个 unittest 测试函数，应该全部通过。

仍然重要的下一步：
- 修复 `config/model_registry.json` 中和 canonical 模型不一致的映射，再运行 `preflight-matrix`。
- 运行 real harness matrix（opencode vs claude-code × 多个模型），优先使用 `calibration`；只解释 `verified_match` 行。
- `bounded` 的时间上限现在会真正限制 adapter 子进程；`open_ended` 无上限。Ctrl-C 后检查 `interruption.json` 和 `checkpoint.json`，再用 `resume` 重跑未保存 result 的 repetition。
- 增加 browser screenshot/pixel visual verification。
- 通过上游 evaluator 导入固定分层的 SWE-bench Verified pilot，再接入 Terminal-Bench。
- 用真实矩阵结果运行 `calibrate-difficulty`，替换通过率过高、过低或没有组合差异的自定义任务。
- `python-bugfix` 已经实测为 smoke-only；它只能验证 adapter 连通性，不能进入比较排行榜权重。
- `audit-corpus` 已是默认 audit 的质量门禁；任何新增或改动的可比较任务必须保持 baseline 失败、reference 通过。
- task run 中断时保留 `runs/<experiment-id>`，读取 checkpoint.json，并用 `resume --experiment-dir` 恢复；suite run 用 `resume-suite --suite-run-dir runs/<suite-run-id>`；matrix run 用 `resume-matrix --matrix-run-dir runs/<matrix-run-id>`。三层都不要重跑已保存的结果，并且恢复时不得绕过 manifest 的任务/组合一致性校验。
- 构建 dashboard 展示历史结果。

请继续以“先架构、再实现、再自检、再更新 handoff/status、最后 commit”的节奏推进。
```
