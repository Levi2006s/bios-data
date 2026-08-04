# 阶段16：Assay 条件化双链位置卷积

## 结论

在 global-family-v2、镜像去重的 543,419/94,848 train/validation 上，assay 条件化重链+轻链位置卷积取得稳定提升。两独立 seed 均超过阶段15，最终粗粒度融合 Spearman 为 **0.460262**，比阶段15的 0.437795 提高 **0.022468**。

| 候选 | Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: |
| 阶段15正式严格候选 | 0.437795 | 0.441323 | 4.150677 |
| 位置卷积 seed 20260807 | 0.451938 | 0.507764 | 4.204445 |
| 位置卷积 seed 20260808 | 0.452994 | 0.506338 | 4.180197 |
| 两 seed 50/50 秩融合 | 0.457651 | 0.477155 | **4.242399** |
| 两 seed 75% + 阶段15 25% | **0.460262** | **0.482392** | 4.231856 |

两个 seed 的预测 Spearman 为 0.931734，既高度一致又保留少量互补。最终只用 5% 步长的粗网格，避免精细权重搜索。

## 模型变化

- 使用真实重链与轻链的固定位置 token，不再忽略轻链。
- 位置保持卷积学习相邻突变组合，而非全局均值池化。
- 两个生物学 landscape 使用 assay embedding 条件化，同时共享底层突变规律。
- pairwise 仅在同一 comparison group 内构造。
- Li affinity1 与 Engelhart 镜像在训练和验证中生物学去重。
- checkpoint 由 global-family-v2 validation Spearman 选择，连续 15 轮无提升早停。

## 分 landscape

最终融合：

- landscape1 Spearman：0.273594；
- landscape2 Spearman：0.655263。

landscape1 仍是绝对瓶颈。训练曲线在相邻 epoch 间波动约 0.01–0.02，说明随机 batch 的同组 pair 密度不足。下一阶段应实现 group-aware batch sampler，并对 landscape1 建显式母本差分/残基上下文专家。

## 产物

- `artifacts/stage16/global_family_v2_deduplicated_assay_positional_conv/`
- `artifacts/stage16/global_family_v2_deduplicated_assay_positional_conv_seed2/`
- `artifacts/stage16/global_family_v2_two_seed_final_ensemble.csv`
- `artifacts/stage16/global_family_v2_two_seed_final_ensemble.metrics.json`

代码测试：68 passed。
