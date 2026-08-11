# 阶段 21：内层 Family Holdout 与母本突变差分

## 结论

阶段 21 首次把模型结构和融合权重选择移到外层训练集内部，最终只对外层 validation 做一次预注册确认。当前严格 Spearman 从阶段 18 的 **0.462209** 提升到 **0.462519**，增加 0.000310。精确抗体对配对 bootstrap 中，新模型优于阶段 18 的概率为 97.2%，但 95% CI 下界略低于 0，因此这是可信度较高但幅度很小的提升。

## 内层 family holdout

仅对 `global_family_v2_split=train` 且路由为 `alphaseq_rank` 的记录重新分折；外层 validation 全部标记为 `excluded`，不参与模型开发。

| 内层折 | 原始记录 | sequence-family 数 |
|---|---:|---:|
| train | 575,105 | 436 |
| validation | 143,776 | 165 |
| excluded | 633,233 | — |

生物学唯一去重后，神经模型实际使用 429,618 条训练记录和 113,801 条验证记录。内层父簇位置卷积基线 Spearman 为 **0.643961**。

## 母本差分编码

对每个 train-only ESM 父簇，以训练序列逐位置多数残基构造重链和轻链共识母本。模型包含两个输入通道：

1. 当前抗体的绝对氨基酸 token；
2. 仅在突变位置非零的 `(母本残基 → 当前残基)` 配对 token。

两个 embedding 拼接后进入位置卷积和 assay/父簇条件化排序头。共识母本和聚类均不读取相应验证折标签。

## 内层选择

| 内层模型 | Spearman |
|---|---:|
| 绝对序列父簇基线 | 0.643961 |
| 母本差分单模 | 0.634570 |
| 67.5% 基线 + 32.5% 差分 | **0.646403** |

差分单模较弱，但与基线预测相关性为 0.952，具有互补排序。权重仅在内层以 2.5% 步长扫描，峰值为 32.5%。

## 外层预注册确认

外层不重新搜索权重。固定公式为：

`77.5% × 阶段17 + 22.5% × (67.5% × 父簇绝对模型 + 32.5% × 母本差分模型)`

等价最终权重：阶段17 77.5%、父簇绝对模型 15.1875%、母本差分模型 7.3125%。

| 指标 | 阶段18 | 阶段21 |
|---|---:|---:|
| Spearman | 0.462209 | **0.462519** |
| Pearson | 0.479374 | **0.480145** |
| landscape1 Spearman | 0.274999 | **0.275867** |
| landscape2 Spearman | **0.656564** | 0.656478 |
| Top-10 enrichment | 4.2150 | **4.2276** |

## 不确定性

以 22,513 个精确重轻链对为 cluster，执行 500 次配对 bootstrap：

- Spearman 增益点估计：+0.000310
- bootstrap 均值：+0.000299
- 95% CI：[-0.000004, +0.000608]
- 候选优于阶段18的概率：97.2%

该结果支持谨慎晋升，但不能描述为大幅或统计上完全确定的突破。

## 产物

- 内层数据：`data/processed/stage21_inner_family_holdout.csv`
- 内层切分摘要：`data/processed/stage21_inner_family_holdout.json`
- 内层聚类：`artifacts/stage21/inner_train_only_esm_parent_clusters_with_references.joblib`
- 内层基线：`artifacts/stage21/inner_parent_conditioned_posconv_baseline/`
- 内层差分模型：`artifacts/stage21/inner_parent_delta_posconv/`
- 外层差分模型：`artifacts/stage21/outer_parent_delta_posconv/`
- 当前推荐预测：`artifacts/stage21/preregistered_outer_parent_delta_ensemble.csv`
- 当前推荐指标：`artifacts/stage21/preregistered_outer_parent_delta_ensemble.metrics.json`
- bootstrap：`artifacts/stage21/preregistered_outer_parent_delta.bootstrap.json`

