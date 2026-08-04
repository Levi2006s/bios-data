# 阶段14：全量数据与全局零重复 family-v2 验证

## 核心结论

本阶段使用全部 1,352,114 条路由记录重建全局 family-v2 fold。旧 `framework_family_split` 在 AlphaSeq train/validation 之间存在 39,272 个完全相同的抗体序列；v2 改为只根据真实重/轻链序列生成 family key，不依赖跨论文可能不一致的 CDR-H3 注释。

v2 AlphaSeq 划分为 train 718,881、validation 162,291、test 218,468，任意两个 fold 的完全相同抗体序列交集均为 0。因此阶段12的 0.668332 只能作为旧 fold 历史指标，不能再解释为零重复的全局泛化成绩。

## 全量训练结果

| 模型 | train / validation | Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: | ---: |
| 全量序列 CNN | 718,881 / 162,291 | 0.324662 | 0.394070 | 3.311585 |
| 全量 ESM2-150M 均值向量头 | 718,881 / 162,291 | 0.324726 | 0.390620 | 3.034952 |
| 全量对齐位置 Ridge | 718,881 / 162,291 | **0.348727** | **0.399962** | 3.230874 |
| CNN 25% + ESM 20% + 位置 55% | 718,881 / 162,291 | **0.356456** | 0.381394 | 3.227178 |

ESM150 对 154,451 条唯一 AlphaSeq 序列生成 640 维 FP16 residue-mean embedding，再映射回全部记录；GPU 为 RTX 4090。CNN 与 ESM 预测 Spearman 相关为 0.7053，存在互补，但全局均值池化丢失关键位点信息，位置 Ridge 仍是最强单模型。

## 关于 0.9

0.9 可以作为研究目标，但当前无泄漏证据只有 0.3565。随机拆分同源突变体、跨来源复用相同序列或在同一验证集反复调权都可能产生接近 0.9 的表面分数，但不能证明比赛测试集泛化。后续只接受 global-family-v2、独立 test 或新 fold 上的提升。

## 下一阶段优先级

1. 从 ESM 的单个均值向量升级为母本—突变体残基级差分表示。
2. 使用 IMGT/ANARCI 编号对齐 CDR 与框架位置，区分重链、轻链和 VHH。
3. 对三个 AlphaSeq assay 建独立专家，再用固定规则路由，避免平台标签互相污染。
4. 使用 comparison-group listwise/pairwise sampler，保证每个 batch 有足够同组样本。
5. 在 v2 test 上只评估一次；validation 用于粗粒度模型选择，不再精细扫权重。

## 产物

- `data/processed/benchmark_team_routed_v6_global_family.csv`
- `artifacts/stage14/esm150_full_alphaseq_embeddings.pt`
- `artifacts/stage14/global_family_v2_full_alphaseq_cnn/`
- `artifacts/stage14/global_family_v2_full_esm150_ranker/`
- `artifacts/stage14/global_family_v2_full_positional_ridge/`
- `artifacts/stage14/global_family_v2_three_model_ensemble.csv`
- `artifacts/stage14/global_family_v2_three_model_ensemble.metrics.json`

代码测试：68 passed。
