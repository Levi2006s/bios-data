# 阶段15：Assay 专家、镜像去重与双链 ESM

## 结果

阶段15继续使用 `global_family_v2_split`，保证 train/validation/test 精确抗体序列交集为 0。

| 模型/口径 | validation n | Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: | ---: |
| 阶段14三路融合，记录口径 | 162,291 | 0.356456 | 0.381394 | 3.227178 |
| 分 assay 位置 Ridge | 162,291 | 0.363568 | 0.425819 | 3.734851 |
| assay + 阶段14融合 | 162,291 | 0.371889 | 0.394194 | 3.587601 |
| 上述融合，生物学唯一口径 | 94,848 | **0.437795** | 0.441323 | **4.150677** |
| 去重单链 ESM150 | 94,848 | 0.382527 | 0.446287 | 3.995699 |
| 去重重链+轻链 ESM150 | 94,848 | **0.395231** | **0.457037** | 3.998861 |

双链 ESM 相对单链提升 0.012704，证明轻链不可忽略。但将它加入当前最佳融合时，最优权重仅 5%，Spearman 只从 0.4377946 变为 0.4377985，增益不足以晋升。

## 镜像数据发现

`li2023 ... affinity1.csv` 与 `engelhart2022 ... affinity.csv` 的 87,807 个唯一重轻链组合、标签和 v2 fold 完全一致，是同一 landscape 的镜像。原始记录口径会把该 landscape 计算两遍。项目保留原始行以便追溯，但训练与主报告新增生物学去重口径。

## 分来源诊断

- Alpha landscape 1/Engelhart 镜像：位置专家 Spearman 0.247541。
- Alpha landscape 2：位置专家 Spearman 0.614154。
- ESM150 train-only cosine kNN：landscape 1 为 0.194180，landscape 2 为 0.581384，总体 0.366405，未晋升。

瓶颈集中在 landscape 1 的家族外泛化。全局 ESM 均值、kNN 和位置模型都无法充分恢复其排序，下一阶段应建母本—突变体残基层差分，而不是继续调融合权重。

## 下一阶段

1. 保存 ESM 每个残基而非仅均值池化，构造 heavy/light 母本差分。
2. 用序列内锚点或 IMGT 编号对齐位置，显式输入 mutation identity、position 和相邻上下文。
3. 对 landscape 1 单独建 parent-conditioned 专家，并用 group-aware listwise batch。
4. validation 只做粗粒度选择，最终在未查看的 v2 test 上一次性复核。

代码测试：68 passed。
