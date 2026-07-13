# Agent Benchmark Lab

一个长期维护的个人 coding-agent 实验室，用来比较真实组合：

```text
harness x model x fixed task cohort x environment x budget profile
    -> raw evidence + multi-dimensional scores + uncertainty
```

它服务于两个不同的问题：

- **当前配置比较**：例如此刻的 Claude Code、opencode、Codex、Aider 分别使用其当前默认模型时，哪个更适合你的实际工作流。
- **严格同模型比较**：只有 adapter 能选择同一模型、并且输出中验证模型身份后，才比较 harness 本身。

它不是模型排行榜，也不会把不同 evaluator 的分数伪装成一个万能总分。

## 当前可用程度

当前版本可以可靠完成：任务隔离、公开/隐藏测试、受保护文件完整性、单题/套件/矩阵运行、可恢复中断、真实 CLI adapter、报告、重复运行统计，以及本地题与官方 SWE-bench evaluator 的分轨报告。

当前版本还**不能**诚实地宣称“Claude Code 比 opencode 强”或“题库已经验证有区分度”：这需要至少三个可识别的真实配置、每个配置至少三次重复，并使用 `screening-report` 证明题目不是过易、过难或无差异。当前筛选就绪题数量为 0；这是严谨的状态提示，不是运行故障。

固定完整卷 `comprehensive-screening-v1` 已可一条命令执行：11 道本地 expert-to-easy 比较题 + 9 道 SWE-bench Verified 高难候选 + 1 道 diagnostic tail。报告输出两条互不混淆的结论：

1. **Local scorecard**：本地十维、verified coverage、领域轴、均值、方差和 CI。
2. **Official SWE resolution track**：官方 evaluator 的 `resolved / scorable attempts` 与 resolution rate。

官方 evaluator 错误不算模型失败；官方结果不进入本地总分、领域轴、雷达图或 matrix 排名。

完整卷还会给出 `balanced-v1` **决策指数**：本地 verified-normalized score 占 55%，官方 SWE resolution rate 占 45%。它是透明的个人选型辅助指标，不是客观总分；当三重复、60% 本地 evidence coverage、9 个官方可评分 attempts 等门槛未满足时，会标为 `provisional`。

## 文档入口

| 读者 | 文档 | 用途 |
| --- | --- | --- |
| 日常使用者 | [用户手册](docs/user_guide.md) | 从环境检查、单题 smoke、矩阵比较到完整卷、统计解释、结果阅读与恢复。 |
| 开发者/下一位 agent | [开发者手册](docs/developer_guide.md) | 架构、目录、任务/adapter/评分扩展、测试与文档维护规则。 |
| 需要判断结果能否对外使用的人 | [基准就绪审计](docs/benchmark_readiness_audit.md) | 已知缺口、科学边界和达到高可信结论的最短路径。 |
| 接手持续开发的人 | [交接文档](docs/handoff.md) 与 [下一 agent 提示词](docs/next_agent_prompt.md) | 当前状态、未完成事项、强制规则、可直接复制的交接 prompt。 |
| 需要理解分数的人 | [评分规范](docs/scoring.md) 与 [能力分类](docs/capability_taxonomy.md) | 权重、证据状态、统计口径和领域轴。 |
| 需要扩展权威题库的人 | [题库策略](docs/corpus_strategy.md) 与 [题目来源](docs/task_provenance.md) | 自建题、SWE-bench、Terminal-Bench 的来源和隔离边界。 |

## 5 分钟验证

浏览器视觉检查首次需要：

```bash
python3 -m pip install -r requirements-browser.txt
npm ci
npx playwright install chromium
```

随后先检查环境和项目自身，不消耗模型额度：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
```

用一个真实 adapter 做低成本连通性验证：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task python-bugfix --adapter claude-code \
  --model unspecified --repetitions 1
```

`--model unspecified` 的含义是“使用该 CLI 当前默认模型并记录实际观察到的身份”，因此它比较的是当前完整配置，而不是同模型 harness 对决。

## 运行完整固定卷

先做不花 token 的预检：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite comprehensive-screening-v1 \
  --adapters claude-code --models unspecified \
  --budget-profiles stress --repetitions 3
```

然后运行：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite comprehensive-screening-v1 \
  --adapter claude-code --model unspecified \
  --budget-profile stress --repetitions 3 \
  --label comprehensive-v1
```

该命令可能运行很久并消耗实际 provider 额度。中断后使用命令输出的目录恢复，不会重新运行已有 summary：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite \
  --suite-run-dir runs/<suite-run-id>
```

报告在 `runs/<suite-run-id>/suite_report.html`、`suite_report.md` 和 `suite_summary.json`。生成历史看板：

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
open runs/dashboard/index.html
```

## 核心规则

- 不要把单次 run、未知模型身份或低 evidence coverage 当作能力排名。
- 每个严肃比较使用同一固定 cohort，至少三次重复；看均值、方差、任务级 95% CI、失败样本和领域轴，不只看 strict total。
- `strict total`、`verified coverage`、`verified normalized score` 必须一起看。未测维度为 0 是保守处理，不等于任务一定失败。
- 工具数不是成本；只有真实 token/cost 会被保存。成本效率要计分时，必须在运行前冻结任务级 `metadata.cost_budget_usd`。
- `external_frozen` 元数据不能被普通 runner 当成权威题；SWE-bench 和 Terminal-Bench 必须走各自官方 bridge/evaluator。
- `runs/` 是证据产物且被 gitignore；不要提交其中的模型日志、patch 或可能包含敏感信息的输出。

完整命令、统计定义、adapter 差异与常见误读，见 [用户手册](docs/user_guide.md)。
