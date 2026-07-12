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

当前仓库是一个可运行的早期 benchmark framework，不是已经完成的权威排行榜。当前有 **19 个任务定义**、7 个 suite、127 个 unittest 测试函数、审计命令和真实 harness 校准路径。

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
- 机器可读题库目录：难度分层为 easy=3、medium=9、hard=4、expert=3；每题都有难度依据和来源类型
- 当前任务是项目自定义 seed/inspired tasks，部分受 SWE-bench、Terminal-Bench 等思路启发；尚未真正导入权威外部题库。详见 `docs/task_provenance.md`。
- `calibration` suite 从易到专家级覆盖本机可运行任务；依赖 Flask、NumPy、SciPy 或 pandas 的任务明确标记为 `container_required`，不会混进默认本机比较。
- Docker evaluator v1：容器任务使用精确版本依赖、隔离 workspace、隐藏测试只读挂载、CPU/内存限制，并保存 Dockerfile、镜像 ID、构建日志与测试证据。容器默认保留网络能力，联网行为应由专门任务和证据单独评估。真实 harness CLI 保持在宿主机登录态运行，并获得同一容器的公开测试脚本。当前 Colima Docker daemon 已可用，且已有 `python-fullstack` 容器运行证据；权威外部题库 evaluator 仍未接入。
- 4 种适配器（dummy/generic-command/opencode/claude-code）
- 真实 harness 输出解析（模型名、工具调用、token、cost）
- 两种明确的模型模式：默认的 `cli_default_configurations` 直接比较两个 CLI 此刻的真实默认配置；显式同模型模式才使用 registry，且跨 harness 的“同模型”结论必须是 `verified_match`，不能只看用户标签。详见 `docs/model_modes.md`。
- `config/model_registry.example.json` 是可选的高级能力：把同一规范模型名映射为 Claude Code / opencode 各自需要的 CLI 参数，避免不同 CLI 命名导致伪同模型比较。
- 矩阵运行与恢复（adapter × model × budget_profile）；每个组合与内部 suite 都有 checkpoint，`resume-matrix` 可补跑未完成组合
- `bounded` 等 profile 会把最长时长传递为真实 adapter 子进程超时；`open_ended` 不限时。Ctrl-C 会保留中断事件、checkpoint 和说明文件，`resume` 只重跑没有 `result.json` 的 repetition。
- 矩阵报告同时展示原始 suite 汇总和仅含 `comparative_candidate` 的排名；排名使用每个任务、每次重复、所有组合共同具备证据的维度，严格分、可验证分、覆盖率、通过率、方差、时长、成本并列展示，`smoke_only` 自动排除出排名。`preflight-matrix` 会在花费 token 前检查统计重复、题目角色、隐藏测试、Docker、适配器和模型映射。
- 公开测试（19/19）+ 隐藏测试（16/19）+ SHA-256 完整性检查
- 静态 HTML 视觉检查
- Playwright Chromium 截图与像素证据：检查元素实际可见、截图非空和像素标准差，PNG 保存到每次 run 的 `visual/` 证据目录
- 过程检查（plan.md、文件变更、测试质量、指令匹配）
- Markdown + HTML 报告（含 SVG 雷达图）
- 自动计算均值、方差、标准差，以及基于 Student-t 的任务级 95% 置信区间（单次 run 不伪造 CI）
- 严格总分 + 已验证证据覆盖率 + 已验证维度归一化分，防止将“暂未测到的维度为 0”误读为能力失败
- `calibrate-difficulty`：依据真实 harness/实际检测模型的多组合、多次运行的通过率与差异判断题目区分度；默认要求每个组合至少 3 次、总计至少 9 次，并排除模型身份未检测到的历史 run
- `screening-report`：区分 smoke、等待真实数据、需要重做、容器题库门未通过和已具筛选性的题；`selection-ladder` 从 expert 到 easy 排列，smoke 题不参与排名
- `preflight-authoritative`：校验 SWE-bench Verified 与 Terminal-Bench 的官方 evaluator 契约、Docker 和本机所需上游工具；它不会把“可执行”误报为“已导入”。
- 每次任务、suite 和 matrix run 都记录完整题目契约指纹；题目内容变化后旧 run 自动退出难度校准和筛选统计，恢复操作也会拒绝混用新旧任务
- 可恢复实验：task run 写入 manifest 和 repetition checkpoint；suite run 也会保存每个任务摘要和 checkpoint。中断后用 `resume` 或 `resume-suite` 仅补做未完成工作。
- Outcome capability scorecard：软件工程、agent 工作流、系统/嵌入式、科学计算/光学、Web/UI、安全可靠性分别汇总，`smoke_only` 任务自动排除出比较分数
- 一键审计、环境诊断、交接提示
- 已有一条真实嵌入式硬题失败校准样本；详见 `docs/real_harness_calibration.md`。单次结果不进入 harness/model 排行榜。

See `docs/roadmap.md` and `docs/handoff.md` before extending the system.

## Quick Start

Browser visual checks need one-time local setup:

```bash
python3 -m pip install -r requirements-browser.txt
npm ci
npx playwright install chromium
```

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-tasks
PYTHONPATH=src python3 -m agent_benchmark.cli.main catalog
PYTHONPATH=src python3 -m agent_benchmark.cli.main calibrate-difficulty
PYTHONPATH=src python3 -m agent_benchmark.cli.main screening-report
PYTHONPATH=src python3 -m agent_benchmark.cli.main taxonomy
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-authoritative
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit --include-real-harness
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
PYTHONPATH=src python3 -m agent_benchmark.cli.main run --task python-bugfix --adapter dummy --model smoke --budget-profile oneshot --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run --task python-bugfix --adapter claude-code --repetitions 1
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume --experiment-dir runs/<experiment-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite --suite-run-dir runs/<suite-run-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-matrix --matrix-run-dir runs/<matrix-run-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix --suite calibration --adapters opencode,claude-code --models unspecified --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite calibration --adapters opencode,claude-code --models unspecified --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --model smoke --budget-profile open_ended --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite calibration --adapter dummy --model smoke --budget-profile open_ended --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite foundation --adapters dummy --models smoke-a,smoke-b --budget-profiles oneshot,open_ended --repetitions 1
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The normal real matrix uses `--models unspecified`: Claude Code and opencode each keep using whichever model the user currently configured in that CLI. This is a practical comparison of current full configurations, not a same-model claim, and reports preserve observed identities. Only use `config/model_registry.example.json` plus an explicit `--models` value for a deliberate same-model experiment; its conclusion still requires saved `verified_match` evidence. See `docs/model_modes.md`.

Run outputs are written under `runs/` by default.

## Safety

API keys, provider credentials, and local harness configuration must be supplied through environment variables or local files excluded by `.gitignore`. This repository should never store secrets.

## Handoff

For context transfer to another agent, use:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
```

The source file is `docs/next_agent_prompt.md`.
