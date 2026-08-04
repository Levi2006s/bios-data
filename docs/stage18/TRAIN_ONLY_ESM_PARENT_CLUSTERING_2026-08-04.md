# 阶段 18：Train-only ESM 母本簇与长度域专家

## 结论

阶段 18 在 `global_family_v2_split`、生物学唯一记录去重的 94,848 条验证记录上，将最终 Spearman 从阶段 17 的 **0.46144** 提升到 **0.46221**。增益为 +0.00077，较小但两个 landscape 均有改善。这个分数是内部严格验证结果，不是 DataCastle 公榜成绩，也不能据此承诺 0.8、0.9 或名次。

## 方法

1. 对重链和轻链分别读取冻结的 ESM-2 150M 表征并拼接。
2. 先按 assay、重链长度、轻链长度分组，仅用训练集唯一序列执行 MiniBatchKMeans，每组 8 簇。
3. 验证序列只分配到最近的训练簇中心；聚类过程不读取验证标签。
4. 将 32 个 `assay|length|cluster` 标识作为位置卷积排序模型的条件嵌入，并把 pairwise 比较限制在同一簇内。
5. 对阶段 17 最终秩与新模型秩做 0%–30%、步长 2.5% 的诊断扫描。最佳 ESM 母本簇权重为 22.5%。该权重是在同一验证集选择的，因此其结果是模型开发指标，不是无偏测试估计。

## 数据覆盖

| 组 | 训练唯一序列 | 验证唯一序列 | ESM 簇数 |
|---|---:|---:|---:|
| landscape1, H117/L108 | 4,409 | 985 | 8 |
| landscape1, H118/L113 | 40,407 | 1,073 | 8 |
| landscape1, H119/L115 | 2,239 | 15,410 | 8 |
| landscape2, H118/L113 | 62,088 | 5,054 | 8 |

H119/L115 是最明显的外推瓶颈：验证唯一序列约为训练的 6.9 倍。

## 指标

| 模型 | Spearman | Pearson | Top-10 enrichment |
|---|---:|---:|---:|
| 阶段 17 最终集成 | 0.46144 | 0.47873 | 4.2572 |
| ESM 母本簇单模 | 0.45253 | 0.50558 | 4.1433 |
| 阶段 18 秩集成 | **0.46221** | **0.47937** | 4.2150 |

分来源 Spearman：landscape1 从 0.27465 升至 **0.27500**，landscape2 从 0.65607 升至 **0.65656**。Top-10 enrichment 下降，因此阶段 18 更适合主指标 Spearman；若赛事同时重视极头部命中，应保留阶段 17 输出作为备选。

## 失败但重要的消融

单独训练 H119/L115 专家使用 9,221 条去重后训练记录和 59,198 条验证记录，80 轮最佳 Spearman 仅 **0.12454**，低于共享模型在该长度组的 0.17859。将它以任意 2.5%–30% 权重用于 H119 内重排都会降低总分，故最终权重为 0，不纳入模型。

这说明问题不是简单的“不同长度应完全拆开”，而是 H119 数据太少，需要共享骨干提供跨长度表示，再做受正则约束的局部适配。

## 下一阶段

1. 从阶段 16/18 全局最优检查点加载共享卷积骨干，而不是随机初始化 H119 专家。
2. 冻结大部分骨干，只训练小型 H119 adapter 或 LoRA 式残差头，并用低学习率防止遗忘。
3. 将序列到训练簇中心的连续距离、局部密度和 OOD 分位数作为门控特征，而非仅使用离散簇 ID。
4. 新建二级验证切分选择融合权重，把主严格 validation 留作近似测试，降低反复调权偏差。

## 复现产物

- 聚类器：`artifacts/stage18/train_only_esm_parent_clusters.joblib`
- 聚类统计：`artifacts/stage18/train_only_esm_parent_clusters.json`
- 母本簇模型：`artifacts/stage18/global_family_v2_esm_parent_conditioned_posconv/`
- 被拒绝的 H119 专家：`artifacts/stage18/h119_l115_esm_parent_expert/`
- 最终预测：`artifacts/stage18/global_family_v2_final_esm_parent_ensemble.csv`
- 完整指标：`artifacts/stage18/global_family_v2_final_esm_parent_ensemble.metrics.json`
- 复现脚本：`scripts/build_stage18_ensemble.py`

