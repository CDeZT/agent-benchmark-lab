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
- README.md

开始工作前先运行：

    PYTHONPATH=src python3 -m agent_benchmark.cli.main status
    PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
    PYTHONPATH=src python3 -m agent_benchmark.cli.main catalog
    PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
    PYTHONPATH=src python3 -m unittest discover -s tests -v

重要规则：
- 不要假打分。没有证据的维度保持 0 或 partial，不要为了好看填分。
- 不要把当前自定义 seed/inspired 任务说成已导入的权威题库；外部导入还没实现。
- 新任务必须声明 `difficulty`、`difficulty_rationale` 和 `provenance`；外部导入任务必须保留上游来源、版本、许可和 evaluator 证据。
- 依赖无法在当前环境复现的任务必须标记 `container_required`，不得混进默认本机比较或把跳过测试当作成功。
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
- 79 个 unittest 测试函数，应该全部通过。

仍然重要的下一步：
- 增加 Docker isolation 和任务依赖 provisioning。
- 运行 real harness matrix（opencode vs claude-code × 多个模型），优先使用 `calibration`。
- 增加 browser screenshot/pixel visual verification。
- 通过上游 evaluator 导入固定分层的 SWE-bench Verified pilot，再接入 Terminal-Bench。
- 构建 dashboard 展示历史结果。

请继续以“先架构、再实现、再自检、再更新 handoff/status、最后 commit”的节奏推进。
```
