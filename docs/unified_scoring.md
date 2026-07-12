# 统一计分：本地题 + 权威题在同一张卷上

## 你要的是什么

权威题 **引进来当题库的一部分**，和本地题 **一起算平均分**，不要两套命令、两套榜。

## 现在怎么用（一条命令）

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite unified-hard \
  --adapter claude-code \
  --repetitions 1
```

套件 `unified-hard` 里：

- 普通 id → 本地测试打分（原来的 10 维）
- `swebench:实例id` → 自动走官方 Docker 验收，**结果写进同一个 suite 报告**

## 权威题在总分里怎么算

| 官方结果 | 这道题在统一卷上的分数 | 会不会拉平均 |
| --- | ---: | --- |
| 修好了 resolved | **100** | 会 |
| 没修好 not_resolved | **0** | 会 |
| 考场挂了 evaluator_error | 不记作模型 0 分 | **不进平均** |

这样权威题就是“题库加分项/拉分项”，不是另一套神秘积分。

## 为什么以前拆开

因为怕：**本地随便判权威题 → 假分**。  
现在改成：**仍用官方判对错，但分数进同一 suite 平均**。

## 和 `swebench-bridge` 单独命令的关系

- 单独 `swebench-bridge` 还能用（调试单题）
- 日常你要“一张卷”：用 `run-suite --suite unified-hard` 即可
