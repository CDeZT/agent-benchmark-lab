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
- docs/model_modes.md
- docs/screening_exam_policy.md
- docs/user_guide.md
- docs/benchmark_readiness_audit.md
- README.md

开始工作前先运行：

    python3 -m pip install -r requirements-browser.txt
    npm ci
    npx playwright install chromium
    PYTHONPATH=src python3 -m agent_benchmark.cli.main status
    PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
    PYTHONPATH=src python3 -m agent_benchmark.cli.main catalog
    PYTHONPATH=src python3 -m agent_benchmark.cli.main calibrate-difficulty
    PYTHONPATH=src python3 -m agent_benchmark.cli.main screening-report
    PYTHONPATH=src python3 -m agent_benchmark.cli.main taxonomy
    PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
    PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
    PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix --suite calibration --adapters opencode,claude-code --models unspecified --repetitions 3
    PYTHONPATH=src python3 -m agent_benchmark.cli.main resume --help
    PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite --help
    PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-matrix --help
    PYTHONPATH=src python3 -m unittest discover -s tests -v

重要规则：
- 不要假打分。没有证据的维度保持 0 或 partial，不要为了好看填分。
- 报告严格总分时，必须同时报告 verified evidence coverage 和 verified normalized score；不要把未测维度导致的低严格分误读为任务失败。
- 不要把当前自定义 seed/inspired 任务或 `external_frozen` 记录说成已导入的权威题库；冻结记录只能通过官方 evaluator bridge 运行，不能进入本地总分或排行榜。
- 新任务必须声明 `difficulty`、`difficulty_rationale` 和 `provenance`；外部导入任务必须保留上游来源、版本、许可和 evaluator 证据。
- 依赖无法在当前环境复现的任务必须标记 `container_required`，不得混进默认本机比较或把跳过测试当作成功。
- `container_required` 任务已有 Docker evaluator v1；当前 Colima Docker daemon 可用，且已有 `python-fullstack` 容器运行证据。保留每次 run 的 `environment.Dockerfile`、`environment.json` 和 `environment-build.log` 作为环境证据。
- 模型并非固定：Claude Code 和 opencode 后面的默认模型会被用户随时调整。普通实测使用 `--models unspecified`，让每个 CLI 使用当下默认模型；这叫 `cli_default_configurations`，是完整当前配置对比，不能写成同模型对比。运行后记录 `default_detected` 或 `default_unverified`。
- `config/harnesses.example.json` 只是新增 headless CLI 的示例，不得把其中名称当作已安装或可运行 adapter。只有内置 adapter、显式本地 `config/harnesses.json` 或 `AGENT_BENCH_HARNESSES_FILE` 指向的 registry 才能进入 `list-adapters` 和真实 run。
- 内置 adapter 现包括 `codex` 与 `aider`。Codex 默认 `exec --json` 的结构化 command/file-change 事件可作为 verified tool telemetry；Aider 未输出结构化 trace 时，workspace diff 只能是 heuristic，不得抬高 verified coverage。两者都必须先通过 `doctor` 与单题真实 smoke，再进入矩阵。
- 只有明确想测“同一模型不同 harness”时，才使用 canonical model + adapter-specific model registry；检查 `model_identity.status`，只有 `verified_match` 才能做同模型结论。不要把 CLI 参数标签、registry 或旧配置当作模型身份事实。
- 在调用真实 harness 前先执行 `preflight-matrix`。如果它报告 registry identity hint mismatch，配置可以用于调试但不可用于公平排名；先修正映射，再花费 token。
- 当前 opencode 1.17.15 的 `--model` 会崩溃，因此其 CLI 默认模型模式是正常且受支持的；即使 registry 写了 opencode 映射，也不能宣称该命令选中了某个模型。
- `swebench-bridge` 是唯一允许把 harness patch 交给官方 SWE-bench evaluator 的路径。默认计划模式不花 token；只有用户明确允许的情况下才加 `--execute`。一次只跑一个 pilot-selected instance；中断时保留 bridge 目录并用同一参数加 `--bridge-dir` 恢复。ARM Mac 必须保持默认空 `--namespace`，让官方镜像本地构建。官方汇总里的 `error_ids` 必须分类为 `evaluator_error`，不可当作模型失败或得分；只有 `resolved` / `not_resolved` 的 per-instance report 才可计分。
- 矩阵的主排名是任务级共同证据维度的 comparable score；严格总分只作诊断。模型身份不是 `verified_match` 的行必须称为 provisional，不能写成同模型结论。
- `cost_efficiency` 的真实 token/cost 必须保存，但只有任务在运行前声明正数 `metadata.cost_budget_usd` 时才可换成分数；不得使用任意美元/ token 换分公式。工具调用次数只能作为 `tool_use` 证据。
- `calibrate-difficulty` 只能按实际检测到的模型身份聚合；默认要求每个 adapter/observed-model/profile 组合至少 3 次、至少 3 个组合和 9 个 eligible run。身份未知或混合的历史 run 只能保留审计，不能凑统计结论。
- 这是筛选性考试，不是合格性题库：先执行 `screening-report`。只有 `selection_ready_local_seed` 才可进入本地选择排名；`smoke_only`、`awaiting_real_evidence`、`retune_or_replace` 和 `corpus_gate_pending` 都不得混入结论。
- `selection-ladder` 必须保持 expert -> hard -> medium -> easy。权威题库以 `config/authoritative_corpora.json` 为准；不得把本地 inspired task 写成 SWE-bench 或 Terminal-Bench 已导入任务。
- 任务内容指纹是结果有效性边界：不得把缺失或不匹配 `task_fingerprint` 的旧 summary 用于难度校准、筛选、排名或胜负结论；任务变动后不得绕过 resume 的指纹拒绝。
- 重复 run 的任务级 95% CI 使用 Student-t（2-30 次）；单次 run 必须显示 CI unavailable。不要为跨任务 matrix 汇总制造一个统计上无意义的总 CI。
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
- task/suite/matrix runner（26 个本地可评测任务、5 个不可运行的 `external_frozen` SWE-bench 元数据记录、13 个套件；`calibration` 覆盖 easy 到 expert，`selection-ladder` 由难到易，`comprehensive-screening-v1` 是固定本地+官方 cohort）。
- public tests + hidden tests。
- SHA-256 protected path integrity。
- static HTML visual checks。
- process planning evidence checks。
- 10 维度评分体系；所有非零分都必须有真实执行证据。
- dummy/generic/opencode/claude-code/codex/aider/grok adapters。
- 真实 harness 输出解析（模型名、工具调用、token、cost），并把 token/cost 汇总进 summary。
- doctor/status/audit 命令。
- 已有历史 real opencode/Claude Code smoke 作为 adapter 调试证据；它们早于任务指纹机制，不能用于当前能力或胜负结论，需重跑。
- 153 个 unittest 测试函数，应该全部通过。
- `agent-benchmark dashboard` 已可从 `runs/` 生成历史 HTML/JSON 看板，并标注 fingerprint 与模型身份是否可用于当前结论。
- `config/model_registry.json` 已去掉 longcat→mimo 伪同模型映射，只保留诚实的 mimo 候选映射。
- `terminal-bench-bridge` 已实现：默认只出 plan，`--execute` 才调用官方 `tb run`；结果在独立 terminal 轨道，不得并入 SWE-bench 分数。
- `comprehensive-screening-v1` 是当前的一键完整筛选卷：11 个本地 expert->easy comparative task、9 个 SWE-bench hard ranking candidate、1 个 diagnostic tail。先用 `preflight-matrix`，再 `run-suite`。官方题通过独立 bridge repetition 运行；报告必须保留本地十维/领域分与官方 resolved/scorable/rate 两条轨道，不能把官方 30 分占位、官方任务或 diagnostic tail 混入本地雷达、平均或排行榜。
- Colima 已提升到 4CPU/8GiB。正在/应继续恢复 `runs/swebench-bridge-sympy-sympy-13878-20260712T084135Z-1c654435` 的官方评测（复用 patch）。
- 实时 fingerprinted CLI-default calibration 矩阵：`runs/matrix-20260712T094706Z-39b0f8c0`。若中断，用 `resume-matrix --matrix-run-dir` 恢复。

仍然重要的下一步：
- 若 live calibration 矩阵仍在跑，等它完成；完成后刷新 `dashboard`、`screening-report`、`calibrate-difficulty`。不要把 CLI-default 行写成同模型结论。
- `bounded` 的时间上限现在会真正限制 adapter 子进程；`open_ended` 无上限。Ctrl-C 后检查 `interruption.json` 和 `checkpoint.json`，再用 `resume` 重跑未保存 result 的 repetition。
- 官方 evaluator 工具现可用：SWE-bench 使用 `.agent-benchmark-evaluators/swebench` 的 Python 3.11，Terminal-Bench 使用 Python 3.13 的 `uv tool`。其他机器先运行 `scripts/setup_authoritative_evaluators.sh` 和 `preflight-authoritative`。工具可执行不等于题目已导入：仍必须冻结上游实例列表并保存官方 evaluator 原始结果。
- 已冻结 `swe-bench-verified-screening-v1` 六题 pilot。`swebench-bridge` 已实现 harness patch -> 官方 evaluator 的单题可恢复链路。首次 expert run 的 patch 已保存；若官方仍 `error_ids`，继续升资源并用同一 `--bridge-dir` 恢复，不得无故重新调用 harness。
- `swebench-pilot` 中另有 5 个历史导入尝试留下的任务记录；它们已被修正为 `external_frozen` + `external_evaluator_only`，用于开发桥接，不是可运行题库。不得重新把通用 `run_evaluation` 写成 task 的 `test_command`。
- 已冻结独立 `terminal-bench-core-engineering-v1` 六题 pilot；通过 `terminal-bench-bridge --execute` 接入官方 `tb run`，结果绝不能和 SWE-bench repository-issue 轨道合并。
- 两个外部 pilot 都是 5 道 `ranking_candidate` + 1 道 `diagnostic_tail`。不得把 tail 题用于排名、平均分或“题库难度”结论；任何新增 pilot 都必须保持复杂候选在前、简单诊断在末尾且至少三道候选。
- 用真实矩阵结果运行 `calibrate-difficulty`，替换通过率过高、过低或没有组合差异的自定义任务。
- `python-bugfix` 是刻意定义的 smoke-only；它只能验证 adapter 连通性，不能进入比较排行榜权重。旧实测不再构成当前难度校准证据。
- `audit-corpus` 已是默认 audit 的质量门禁；任何新增或改动的可比较任务必须保持 baseline 失败、reference 通过。
- task run 中断时保留 `runs/<experiment-id>`，读取 checkpoint.json，并用 `resume --experiment-dir` 恢复；suite run 用 `resume-suite --suite-run-dir runs/<suite-run-id>`；matrix run 用 `resume-matrix --matrix-run-dir runs/<matrix-run-id>`。三层都不要重跑已保存的结果，并且恢复时不得绕过 manifest 的任务/组合一致性校验。
- Dashboard 静态历史视图已存在；如需再做 live server 或多矩阵趋势图，应在有更多 fingerprinted matrix 证据后进行。

请继续以“先架构、再实现、再自检、再更新 handoff/status、最后 commit”的节奏推进。
```
