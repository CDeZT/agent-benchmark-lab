# 用大白话说明：这套系统在干什么

## 你的要求（翻译成普通人能懂的话）

1. 用 **Claude Code / opencode / Grok** 真做题、真打分  
2. 题要 **多一点、难一点**，最好用 **公认权威题库** 里的题  
3. **光学要有区分度**（不能只有一两道）  
4. **题目和答案要分开**：agent 只能看到题目工作区，隐藏测试/标准答案不进工作区；评测尽量在 **Docker 干净环境** 里跑  
5. 分数要真实，**不要假分**；能打的维度别无故给 0  
6. 要有 **雷达图**（过程 10 维 + 领域轴）  
7. 自己先能用起来；**远未宣称做完**，要持续迭代  

## 现在技术怎么走（一条线）

```
出题（本地题 或 权威题）
   → 复制「题目工作区」到隔离目录（不含 hidden/solution）
   → 启动某个 agent 改代码
   → 在 Docker 里跑公开测试 + 隐藏测试（题/答分离）
   → 看改了哪些文件、有没有计划、工具/花费证据
   → 打出分数 + 雷达图 + 报告
```

### Docker 是干什么的？（题 / 答分离）

| 角色 | 看到什么 |
| --- | --- |
| Agent | 只有 `workspace`（题目代码） |
| 评分器 | 额外挂载 `hidden/`（隐藏测试，只读），在 Docker 里跑 |
| 答案参考 `solution/` | **从不**给 agent，只给人对照 |

- **Python / 光学本地题**：现在默认倾向 `container_required`（Docker 打分）。  
- **权威题（SWE-bench）**：官方 Docker 验收。  
- **C / 前端 / 主机工具链题**：有的仍是 `local`（主机编译/Playwright），**这是还在补齐的缺口**，不是“已经全部 Docker 了”。

## 光学题：不是两道，是一整个梯子

套件：`optics-discrimination`

| 难度 | 任务 id | 内容 |
| --- | --- | --- |
| easy | optics-thin-lens | 薄透镜成像 / 放大率 |
| medium | optics-python | 强度剖面归一化 |
| medium | optics-interference | 双缝条纹间距 / 光程差 |
| medium | optics-snell | 折射 + 临界角（TIR） |
| hard | optics-psf-peak | PSF 峰 + 半高宽插值 |
| hard | optics-gaussian-beam | 高斯光束腰、瑞利距、曲率 |
| hard | optics-imaging-pipeline | 暗场/平场/坏点/模糊流水线 |
| hard | optics-abcd | 光线 ABCD 矩阵级联 |

全部是 **Docker + workspace/hidden 分离**。

## 雷达图在哪

| 图 | 位置 | 含义 |
| --- | --- | --- |
| 过程 10 维雷达 | 每次任务 `runs/<id>/report.html` | 完成度、计划、工具、安全边界… |
| 领域轴雷达 | suite 跑完后 `runs/suite-*/suite_report.html` | 软件工程 / 系统嵌入式 / **科学计算与光学** / Web / 安全… |
| 历史面板 | dashboard | 最近几次任务雷达缩略 |

光学题跑多了，`scientific_computing` 轴才有数；以前题太少，轴经常缺失或没区分度——这是你说对的点。

## “权威题”是什么，分数是什么

| 说法 | 人话 |
| --- | --- |
| 权威题库 | 别人做好的、公认的难题集（如 SWE-bench） |
| 引进题库 | 拉进来让 agent 做 |
| 统一分数 | **同一 suite 里本地题 + 权威题一起平均**；官方修好=100，没修好=0；考场环境失败不算模型 0 分 |

```bash
# 光学区分度卷
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite optics-discrimination --adapter claude-code --repetitions 1

# 难一点的本地综合卷（含更多光学难题）
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite hard-discrimination --adapter claude-code --repetitions 1

# 本地 + 权威统一卷
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite unified-hard --adapter claude-code --repetitions 1
```

## 还明确没做完、还要迭代的地方

1. **不是所有题种都 Docker 了**：C/嵌入式/并发/前端视觉等仍可能 host 评测。  
2. **权威难题批量实跑** 仍在进行（慢、镜像/OOM/无 patch 要处理）。  
3. **工具遥测**：Claude/Grok 有时只给粗代理，`tool_use`/`cost` 证据强度仍可加强。  
4. **光学以外的域题库深度**（嵌入式协议、系统编程）还可以再加硬梯。  
5. **统计稳定性**：区分度套件需要多 harness × 多 repetition，不能只看一次 smoke。  
6. **开放标准 / 对外发布** 仍是次要目标；先服务你自己能稳定打分。

**结论：还在迭代，不该说“做完了”。** 当前这一轮补的是：Docker 题答分离策略、光学题量与梯子、suite 领域雷达。
