# 阶段 9：认证表驱动的 assay-safe 标签重建

日期：2026-08-03

## 当前状态

已根据标签认证审计生成实验性 `benchmark_assay_safe_v4.csv`，不覆盖 v3。v4 保留全部 1,352,114 个 record_id、序列和 framework-family 划分，只修改 AbRank 的 `score`、`metric` 与 `comparison_group`。

## AbRank 重建

原始 AbRank 监督记录按以下键形成比较组：

```text
source_file :: Source :: endpoint :: antigen_id
```

结果：

- AbRank 记录：169,130
- KD：94,686
- IC50：74,444
- comparison groups：5,620
- 单例组：1,385；组内无可辨识排名，当前 score 暂为 0.5
- 新旧 AbRank score Spearman：0.855553
- 新旧 score 平均绝对变化：0.122940
- v3/v4 非预期字段差异：0

## 点回归负结果

使用相同 ESM embeddings、数据划分、种子和任务头超参数训练 v4 点回归模型：

- v4 全局 Spearman：0.271760
- v4 Top-10 enrichment：2.759365
- 旧 v3 模型在 v4 comparison group 内 macro Spearman（n>=5）：0.508974
- v4 点回归模型在相同组内 macro Spearman：0.395786

该结果不是 assay-safe 标签思想失败，而是说明“每组重新缩放后继续做跨组点回归”的目标不匹配。旧全文件百分位是原始标签的单调变换，因此仍保持局部次序；v4 的不同小组 0–1 标尺不应通过 MSE 强行校准。

## 下一模型

已实现 `esm_pairwise.py`：

- 只在同一 comparison group 内构造偏好对；
- 从阶段 6 最佳 ESM 头初始化；
- 使用 `softplus(-(s_high-s_low))` pairwise logistic loss；
- 使用 n>=5 comparison group 的 macro Spearman 选择 checkpoint；
- 不允许大来源按记录数支配模型选择。

新增测试后全套为 60 passed。

## Pairwise 实验结果

### 全终点模型

全终点组内 pairwise 模型使用 46,746 个偏好对，最佳第 7 轮：

- 181 个可评估组 macro Spearman：0.519219
- 旧模型相同组：0.491077
- 平均提升：+0.028142
- 组级 bootstrap 正提升概率：96.15%
- 95% 区间：[-0.002684, 0.058651]
- Top-10 enrichment：2.867812

提升主要来自 AbRank IC50（0.517195 → 0.555343），KD 子集下降。因此该 checkpoint 定位为功能排序实验模型，不替换亲和力主模型。

### KD-only 组平衡模型

只保留 `AbRank_KD`、`KD`、`negative_log10_KD`，每个训练 comparison group 最多 2,048 对。实际使用 7,078 条训练记录、2,994 个偏好对。最佳第 18 轮：

- 9 个可评估 KD 组 macro Spearman：**0.313341**
- 旧模型相同组：0.185922
- 平均提升：+0.127418
- 改善组：6/9
- bootstrap 正提升概率：94.64%
- 95% 区间：[-0.021325, 0.300341]
- 中位数组内 Spearman：0.250720

最大 AlphaSeq 组从 0.2795 降到 0.2105，但多个小型真实 SPR/KD 组改善。该模型定位为跨来源 KD 专家；由于只有 9 个组且区间跨 0，暂不替换正式提交模型。

### 教师锚定负结果

为保留旧模型的大组表现，测试了成对分差 MSE 锚定：

| anchor weight | macro-group Spearman | record-weighted Spearman | 判断 |
| ---: | ---: | ---: | --- |
| 0 | **0.313341** | 0.211815 | 最强跨组 KD 专家 |
| 0.02 | 0.274796 | 0.223957 | 折中但不占优 |
| 0.2 | 0.207686 | 0.261538 | 过强，抑制适应 |
| 旧模型 | 0.185922 | **0.277429** | 最大组稳定 |

简单教师锚定无法同时提升宏平均与记录加权指标，停止继续扫描以避免在 9 个验证组上过拟合。

## 当前模型决策

- 赛事全局提交：继续使用阶段 6 的 ESM+CNN 秩融合，保持与官方/旧标签口径一致。
- 跨来源定量亲和力：使用无锚定 KD-only pairwise 专家进行候选复核。
- IC50/功能效力：保留全终点 pairwise 模型作为独立功能专家。
- 不把 KD、IC50 与 OVA 风险重新混成单个无条件标量。
