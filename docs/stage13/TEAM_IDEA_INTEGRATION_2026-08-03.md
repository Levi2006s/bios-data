# 阶段13：队友资料复核与全队方案整合

## 结论

两份队友资料有用，但不同实验终点不能直接并入一个回归头。阶段13已落实：**标签可信度路由、多任务隔离、数据集温度采样、同实验组 pairwise，以及“缺抗原辅助预训练 → 完整双序列微调”接口**。

正式模型仍是阶段12的母本簇位置互作 + ESM150 + CNN 域路由集成：严格 framework-family validation Spearman **0.668332**，Pearson **0.682585**，Top-10 enrichment **4.875429**。阶段13两阶段 CNN 已完成，但没有超过正式模型，不得声称达到 0.8。

## 资料复核与决策

- 采用 A/B/C/D/NA 标签等级，但等级只控制 loss weight，不作为预测标签。
- KD/pKD 进入 `affinity_rank` 主任务；AlphaSeq 以 B 级 0.6 权重进入独立组内排序。
- EC50、IC50、binding、ADCC、OVA 分别路由；OVA 是风险方向，ADCC 不进入亲和力主头。
- 采用 `p(d) ∝ min(n_d, cap)^alpha` 数据集温度采样，默认 alpha 0.4。
- 修正 pairwise：只在相同 `comparison_group` 内产生比较，禁止跨 assay 随机配对。
- Fab/scFv/VHH/IgG 保留格式字段；VHH 与 mAbs/Fv 最终分专家路由。
- 抗体专用 LM、ESM 抗原编码和 CDR—抗原 cross-attention 保留为后续升级，必须通过严格新 fold 才晋升。

## 全量数据路由

`data/processed/benchmark_team_routed_v5.csv` 已对 **1,352,114 / 1,352,114** 条整理记录完成路由：

| 路由 | 条数 | 缺抗原序列 |
| --- | ---: | ---: |
| AlphaSeq 组内排序 | 1,099,640 | 1,099,640 |
| AbRank 组内排序 | 169,130 | 20,500 |
| KD/pKD 亲和力主任务 | 81,965 | 81,601 |
| IC50 辅助 | 577 | 577 |
| EC50 辅助 | 345 | 0 |
| 相对 binding 辅助 | 222 | 222 |
| OVA 多反应性风险 | 222 | 222 |
| ADCC 辅助 | 13 | 13 |

因此，“全部数据做了一遍”的精确定义是：**标签治理和任务路由是全量；抗原条件主模型训练不是全量，因为多数公开记录没有抗原序列。** 空抗原不能伪装成真实抗原。

## 整合后的训练路线

1. B 级 AlphaSeq 等缺抗原、同靶点大规模 landscape 训练抗体编码器，只学习组内排序。
2. 将辅助 checkpoint 迁移到双序列模型，用 A 级 KD/pKD 和真实抗原序列低学习率微调。
3. EC50、IC50、binding classification、OVA risk 分头训练；缺失标签只更新对应 head。
4. 用 framework-family、antigen holdout、double holdout 和 study/platform holdout 组成验证矩阵。
5. 只有新模型在固定严格集超过 0.668332、多个 seed 一致且 cluster bootstrap 稳定，才能替换阶段12。

## GPU 恢复后的续跑命令

```bash
PYTHONPATH=src python -m bioos_benchmark.neural_ranker \
  --input data/processed/benchmark_team_routed_v5.csv \
  --artifact-dir artifacts/stage13/team_alphaseq_antibody_pretrain \
  --seed 20260803 --epochs 3 --batch-size 512 --learning-rate 3e-4 \
  --max-rows-per-source 100000 --rank-loss-weight 0.5 \
  --include-task-routes alphaseq_rank --sampling-alpha 0.4 \
  --sampling-cap 200000 --allow-missing-antigen

PYTHONPATH=src python -m bioos_benchmark.neural_ranker \
  --input data/processed/benchmark_team_routed_v5.csv \
  --artifact-dir artifacts/stage13/team_trusted_finetune \
  --initialize-from artifacts/stage13/team_alphaseq_antibody_pretrain/model.pt \
  --seed 20260803 --epochs 8 --batch-size 256 --learning-rate 5e-5 \
  --max-rows-per-source 100000 --rank-loss-weight 0.5 \
  --include-task-routes affinity_rank abrank_group_rank \
  --sampling-alpha 0.4 --sampling-cap 200000
```

## 实际 GPU 训练结果

GPU 在默认沙箱内不可见，但在允许访问宿主设备后确认并使用了 NVIDIA GeForce RTX 4090（23,028 MiB）。

| 阶段 | train / validation | 最佳 Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: | ---: |
| AlphaSeq 抗体侧辅助预训练 | 206,858 / 49,295 | 0.383136 | 0.385997 | 2.484535 |
| 真实抗原主任务迁移微调 | 48,376 / 16,599 | **0.485555** | 0.518185 | 3.035962 |

辅助预训练三轮 Spearman 从 0.355587 升至 0.383136；迁移微调最佳出现在第 6/8 轮。说明辅助表征可以迁移，但轻量 CNN 容量仍不足以替代阶段12。

按 `record_id` 与阶段12对齐后，共有 16,599 条共同验证记录。阶段12在该子集为 0.663320，新模型为 0.485555，预测 Spearman 相关为 0.696279。百分位秩融合扫描在新模型权重 2.5% 时达到 0.663502，仅提升 0.000182；该差值过小且是在同一验证集选权重，故拒绝晋升。

代码验证为 **66 tests passed**。下一步应把已验证的数据路由和辅助预训练迁移到 ESM150/抗体专用编码器，而不是继续增加轻量 CNN epoch。
