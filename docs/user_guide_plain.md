# 用大白话说明：这套系统怎么用

## 目标

用真实 coding agent（Claude Code / opencode / Grok）做题、在 **Docker 里题答分离打分**，得到可证据追溯的分数和雷达图。  
**不是**做完的权威排行榜；权威 SWE 题另走 bridge，且禁止无 patch 空转重试。

## 题 / 答分离

| 谁 | 看到什么 |
| --- | --- |
| Agent | 只有 `workspace`（题目） |
| 评分器 | 额外只读挂载 `hidden/`，在 Docker 里跑测试 |
| `solution/` | 只给人对照，永不给 agent |

多数 **Python / 光学** 题是 `container_required`（Docker 打分）。  
**C / 嵌入式 / 并发** 用本机编译器（host），仍是 workspace/hidden 分离。  
前端视觉题在 host（Playwright）。

## 现在有什么题

- **本地可跑题**：约 26 道（含光学梯子 8 道 + C/嵌入式 Docker）
- **权威 pilot（配置里选中）**：SWE-bench Verified 10 + Terminal-Bench 6  
- **已有官方结论的 SWE 实跑**：flask 通过、pylint 未通过；pytest 无 patch 已禁止无意义 resume

## 推荐用法（先可用）

```bash
# 1) 框架自检
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor

# 2) 假 agent 冒烟（不烧 token）
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task optics-thin-lens --adapter dummy --repetitions 1

# 3) 真实 agent 测一题
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task optics-thin-lens --adapter grok --repetitions 1
# 或 --adapter claude-code / opencode

# 4) 小套件
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite personal-probe --adapter claude-code --repetitions 1

# 5) 光学区分度
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite optics-discrimination --adapter claude-code --repetitions 1
```

报告：

- 单题雷达：`runs/<id>/report.html`
- 套件领域雷达：`runs/suite-*/suite_report.html`

## 权威题（SWE）注意

```bash
# 计划（不烧 token）
PYTHONPATH=src python3 -m agent_benchmark.cli.main swebench-bridge \
  --instance-id pallets__flask-5014 --adapter opencode

# 执行：有 harness 超时；patch_missing 后默认拒绝 resume
PYTHONPATH=src python3 -m agent_benchmark.cli.main swebench-bridge \
  --instance-id pallets__flask-5014 --adapter opencode --execute \
  --harness-timeout-seconds 2400

# 若明确要在 patch_missing 后再试：
#   --retry-harness
```

统一卷（本地难 + 已可计分官方题）：`run-suite --suite unified-hard`。

## 还没做完（诚实）

- Terminal-Bench 批量官方结果仍少  
- 部分超难 SWE 镜像/TLS 会失败（算环境失败，不算模型 0）  
- 前端视觉 Docker 化未做  
- 多 harness 统计矩阵要你自己按 token 预算跑  

**当前“可用”定义**：validate 过、Docker 题答分离打分稳、套件齐、真实 agent 能跑通一题并出报告。
