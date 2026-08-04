# 阶段 11：全量排序、ESM2-150M 与 AlphaSeq 域路由

## 结论

严格 `framework_family_split=validation` 上，最终无泄漏 Spearman 为 **0.660689**，高于阶段 10 的 0.460773。目标 0.8 尚未达到，不应写成已达到。

## 关键发现

- 可用验证 27,924 条，其中 AbRank 27,834 条（99.68%）。
- 旧神经训练每来源最多抽样 50,000 条，实际只使用 22k 左右 AbRank train；取消错误截断后使用 81,740 条完整 train。
- 同输入冲突只涉及 221 条；按相同输入取验证组均值的理论 Spearman 约 0.998，标签冲突不是主要数学上限。
- AlphaSeq 占验证 21,289 条，是主瓶颈。ESM 域内 Spearman 约 0.467；CATNAP 已达 0.734。

## 模型升级

| 模型 | 严格 Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: |
| 阶段 10 高分候选 | 0.4608 | 0.5200 | 2.7835 |
| 全量 CNN 回归 | 0.5086 | 0.5754 | 2.3088 |
| 全量 CNN + pairwise rank | 0.5556 | 0.6192 | 3.6727 |
| ESM2-150M 全量 rank-aware | 0.6133 | 0.6801 | 4.0700 |
| ESM2-150M + 同抗原条件排序 | 0.6161 | 0.6819 | 4.1488 |
| **域路由最终集成** | **0.6607** | **0.6781** | **4.7179** |

最终集成先在 AlphaSeq 内用 65% 位置一热 Ridge 与 35% ESM 专家做秩融合，再把该域的秩分位映射回全局 ESM 分布。全局权重为：80% 域路由模型、13.33% CNN-rank、6.67% CNN-reg。

## 为什么位置模型有效

AlphaSeq 是少数母本周围的定点突变景观：只有 3 个宽抗体簇和 1 个抗原簇。ESM 均值池化与 CNN 最大池化会弱化绝对位置信息；位置对齐的一热 Ridge 直接估计“位置 × 氨基酸”的加性突变效应，在 AlphaSeq 上达到 0.5274，超过专用 ESM 头的 0.4752。

## 可复现产物

- `artifacts/stage11/final_domain_routed_ensemble.csv`
- `artifacts/stage11/final_domain_routed_ensemble.metrics.json`
- `artifacts/stage11/esm2_t30_150m_embeddings.pt`
- `scripts/build_stage11_ensemble.py`
- `scripts/build_abrank_domain_dataset.py`
- `src/bioos_benchmark/positional_ranker.py`

## 风险边界

0.6607 是在同一固定 validation 上选择若干权重后的候选分数，仍需新 fold 或最终 test 复核选择偏差。若不读取验证标签、只使用 train 标签和输入序列，当前实验没有证据支持 0.8。达到 0.8 需要显著改善 AlphaSeq 家族外泛化，可能依赖端到端残基层微调、显式位点互作或结构/表位信息。
