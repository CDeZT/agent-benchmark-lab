# 用大白话说明：这套系统在干什么

## 你的要求（翻译成普通人能懂的话）

1. 用 **Claude Code / opencode / Grok** 真做题、真打分  
2. 题要 **多一点、难一点**，最好用 **公认权威题库** 里的题  
3. 光学也要有  
4. 分数要真实，**不要假分**；能打的维度别无故给 0  
5. 自己先能用起来  

## 现在技术怎么走（一条线）

```
出题（本地题 或 权威题）
   → 复制到隔离工作区
   → 启动某个 agent（Claude/opencode/Grok）改代码
   → 跑公开测试 + 隐藏测试
   → 看改了哪些文件、有没有计划、工具/花费证据
   → 打出分数 + 雷达图 + 报告
```

**Docker 是干什么的？**  
权威题（比如 SWE-bench）要在“官方考场环境”里验收。Docker 就像一台干净的考试电脑：装好依赖再跑官方验收。  
**本地小题目** 多半不用 Docker；**权威大题** 需要 Docker（你机器上 Colima 就是在跑 Docker）。

## “权威题”是什么，分数是什么

| 说法 | 人话 |
| --- | --- |
| 权威题库 | 别人做好的、公认的难题集（如 SWE-bench：修真实开源项目 bug） |
| 引进题库 | 把这些题拉进来让 agent 做 |
| 分数 | **这题修好了没**（官方验收：修好/没修好）+ 我们自己的过程分（计划、工具等） |

不是两套玄学积分。就是：**用难的真题，用真验收。**

## 实现到哪了

| 你的要求 | 现在 |
| --- | --- |
| 三个 agent 真跑 | 已做到 |
| 本地打分 + 雷达 | 已做到 |
| 光学题 | 有 2 道可用（normalize + PSF 峰/半高宽） |
| 难题套件 | `hard-discrimination` |
| 权威题引进 | **进行中**：已有难向 pilot（9 道难/中难 + 1 道诊断），并已成功官方判分至少 1 道；正在继续多跑 |
| tool_use 无故 0 | **已修**：有改文件或有工具日志就给分 |

## 还差什么

- 权威题 **批量** 跑完还需要时间（每道都要 Docker + agent 做题，很慢）  
- 更难的官方题有时环境镜像会失败，失败不算模型 0 分，是考场没搭好  
- Grok 有时不报花费，花费维度仍可能是 0（它没给数据）  

## 你怎么用

```bash
# 难一点的本地套题
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite hard-discrimination --adapter claude-code --repetitions 1

# 权威题（一道）
PYTHONPATH=src python3 -m agent_benchmark.cli.main swebench-bridge \
  --instance-id pytest-dev__pytest-10356 --adapter opencode --execute
```


## 统一卷（本地+权威一起算）

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite unified-hard --adapter claude-code --repetitions 1
```

权威题用 `swebench:实例id` 写在同一 suite 里；官方修好=100，没修好=0，和本地题平均。详见 `docs/unified_scoring.md`。
