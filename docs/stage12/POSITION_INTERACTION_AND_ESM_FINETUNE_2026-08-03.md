# 阶段 12：位置互作、母本簇路由与 ESM 残基层微调

严格框架家族 validation 的最终候选 Spearman 为 **0.66833**，阶段 11 为 0.66069。目标 0.8 仍未达到。

## 新模型

| AlphaSeq 专家 | 域内 Spearman |
| --- | ---: |
| 全局位置 Ridge | 0.52737 |
| 位置保持卷积，seed48 | 0.53407 |
| 位置保持卷积，seed51 | 0.52116 |
| ESM2-150M 最后一层微调 | 0.47734 |
| 母本簇位置 Ridge | 0.54144 |
| **五路域内秩融合** | **0.56073** |

完整验证再与 CNN-rank/CNN-reg 融合后为 0.66833，Pearson 0.68259，Top-10 enrichment 4.87543。ESM 微调使用共享单抗原编码，batch 128 时 RTX 4090 显存约 2.9GB；该优化显著降低重复计算。

## 关键诊断

AlphaSeq 有三个宽母本簇。最大验证簇的 train/validation 数量为 4,220/20,944，严格切分高度不平衡。单一共识下样本中位“突变数”达到 163，说明必须先识别母本，再学习母本内突变效应。

当前 0.66833 已使用多次固定 validation 选择权重，存在选择偏差；在新 fold 或 test 复核前不能声称达到 0.8。

## 产物

- `artifacts/stage12/final_parent_cluster_routed_ensemble.csv`
- `artifacts/stage12/final_parent_cluster_routed_ensemble.metrics.json`
- `src/bioos_benchmark/positional_neural_ranker.py`
- `src/bioos_benchmark/cluster_positional_ranker.py`
- `src/bioos_benchmark/esm_finetune.py`
