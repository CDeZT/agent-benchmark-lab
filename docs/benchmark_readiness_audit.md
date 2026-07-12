# Benchmark Readiness Audit

日期：2026-07-12。本文按严肃 coding-agent benchmark 的标准审计当前仓库，而不是为项目背书。结论：**它已适合个人的可重复实验，但尚不适合发布为权威、普适的排行榜。**

## 审计方法

本轮检查了：`doctor`、`catalog`、`audit-corpus`、`screening-report`、`preflight-matrix`、评分实现、adapter/telemetry 边界、隔离设计、外部 evaluator bridge、文档和单元测试。没有把“命令存在”或“单题曾通过”误写为总体能力结论。

## 当前证据

| 项目 | 结果 | 解读 |
| --- | --- | --- |
| 任务记录 | 31 | 26 本地题 + 5 个 frozen SWE-bench metadata 记录。 |
| 难度 | easy 7 / medium 11 / hard 9 / expert 4 | 作者声明覆盖足够，但尚未由通过率校准。 |
| 基线/参考解门 | 21 通过 | 这些题已经证明“错误基线失败、参考解通过”。 |
| 容器题质量门 | 5 待补 | 依赖包题被 host-only corpus audit 跳过，不能被误称为已验证对比度。 |
| 筛选就绪题 | 0 | 当前没有任务满足多配置、多重复、已识别模型的经验判别门。 |
| 本机 harness | Codex、Aider、Claude Code、opencode、Grok 都被 doctor 检测到 | 表明可开始实测，不表明各 provider 当前认证、模型可用或模型身份一定可解析。 |
| 外部 evaluator | SWE-bench / Terminal-Bench 工具链可预检 | 每个官方任务仍须保存独立官方结果。 |

## 已经做对的地方

1. **任务/答案隔离和隐藏测试**：agent workspace 不含 `solution/`，隐藏测试独立评分；受保护路径用 SHA-256 检查。
2. **没有把冻结元数据当作导入题**：外部任务只有官方 evaluator 输出后才 scoreable；评测器错误不会记成模型 0 分。
3. **重复、恢复和可追溯性**：run 保存 manifest、checkpoint、trace、diff、stdout/stderr、任务指纹和报告；中断可恢复。
4. **多种结果视图**：严格分、verified coverage、verified normalized score、共同证据的 comparable score 和领域轴分数同时存在，避免只报一个好看的总分。
5. **明确的同模型边界**：当前默认配置比较与 verified same-model 比较被区分，opencode 的显式模型限制被暴露。
6. **多领域与高难任务**：嵌入式、系统 C、并发、光学、全栈、安全和复杂 bugfix 都已有可运行样本，且有 hard/expert 轨道。

## 未达到“权威”要求的缺口

### P0：没有经验上的题目区分度证据

所有本地 comparative task 都仍是 `awaiting_real_evidence`，筛选就绪题为 0。当前 hard/easy 标签只是设计假设。要声称“这套题能分开强弱 agent”，至少要固定一个 cohort，使用至少 3 个已识别配置、每个 3 次，并基于通过率、方差和 task-level CI 把过易、过难或无差异题 retune/replace。

### P0：五个依赖包容器题没有完成基线/参考解 corpus audit

Docker runner 能执行这些题，但质量门没有在相同 Docker 环境验证 untouched baseline fail/reference pass。应新增 Docker-backed corpus audit，再允许这些题从 `corpus_gate_pending` 进入选择池。

### P0：成本分的跨 provider 可比性不足

当前成本 telemetry 依赖 CLI 暴露的 token/cost；不同 provider 的 token 定义、缓存、价格和遥测完整度不同。实现已移除任意全局 token/cost 换分，未声明任务预算时成本仅作为单独观测。后续若要计入效率维度，必须在运行前冻结任务级预算或固定价格表、上下文量、缓存与成功质量的归一化协议。

### P1：过程维度仍有代理指标

`intent_understanding`、`execution_quality`、`planning` 主要看题目预先声明的文件/产物；这足以做可执行检查，但不等于真正理解需求。`instruction_match` 已明确降为 heuristic intent evidence。`self_repair` 仍是日志关键词 heuristic。工作区 diff 作为 `tool_use` fallback 已降级为 heuristic；只有结构化 CLI 工具事件才可抬高 verified coverage。下一步应保存测试前后序列、失败到修复的因果链、子代理调用和浏览器行动日志。

### P1：统计设计还不完整

已有任务级 Student-t CI，但缺少配对显著性检验、effect size、多任务多重比较控制、预注册 cohort/权重和固定随机性策略。正式比较至少应固定：CLI 版本、模型身份、任务 commit/hash、预算、并发、Docker 镜像和网络策略。

### P1：本地自建题与公开污染风险

项目自建题对开发者和未来模型可能可见，公开测试也可能被记忆。隐藏测试和答案隔离减轻了运行时泄漏，但不能消除训练数据污染。外部任务要固定 release、实例列表和采样规则；本地题要轮换隐藏测试、引入 holdout cohort，并记录何时公开过题干。

### P2：外部轨道的合并解释需要更严格

SWE-bench repository issue、Terminal-Bench terminal task 和本地任务的成功率含义不同。即使存在 `unified-hard`，对外报告仍应默认分轨展示；若合并，必须预先公布映射、权重、诊断题排除规则和不确定性。

### P2：缺少独立复核与人类裁决协议

复杂开放题、视觉质量、计划质量和安全审查可以加入双盲人工复核或独立 judge，并预先定义分歧阈值、第三裁决者、评分 rubric 和一致性指标。judge 只能补充，不能覆盖可执行测试。

## 走向高可信基准的最短路径

1. 对 `hard-discrimination` 固定 6-10 道题，运行 Codex、Aider、Claude Code、opencode、Grok 中至少 3 个可识别配置，每个 3 次。
2. 记录每次的 CLI 版本、默认模型/显式模型、provider、token/cost、Docker image、任务 fingerprint、开始时间和预算 profile。
3. 完成五个容器题的 Docker corpus audit；失败的 baseline/reference 立刻修题或移出候选池。
4. 用 `calibrate-difficulty` 和 `screening-report` 只保留真正 `selection_ready_local_seed` 的题进入主排名；smoke、diagnostic tail、容器质量门待补和 evaluator failure 不进入平均。
5. 分别报告 task pass rate、verified normalized score、coverage、耗时、成本、领域轴和 CI；不只报一个总分。
6. 完成至少一个 hard ranking SWE-bench 实例和一个 Terminal-Bench 实例的官方 scoreable 结果，保持独立轨道。
7. 发布前冻结版本和运行脚本，让第三方可以在不读取隐藏测试/答案的前提下复跑。

## 最终判断

**适合现在使用**：个人选择当前 CLI 默认配置、发现一个 agent 的明显失败模式、比较领域能力、积累可恢复的真实运行证据。

**不应现在宣称**：某个 harness 在所有模型/任务上更强、任意总分是普适排行榜、题库难度已经经验校准、不同 provider 的成本分可直接横比。

这不是缺点被掩盖，而是让后续每一轮真实运行都能减少一个明确不确定性，而不是继续堆更多看似完整的功能。
