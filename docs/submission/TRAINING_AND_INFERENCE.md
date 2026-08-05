# AbCompass 训练、优化、推理与测试技术文档

## 可复现结论

当前正式训练入口是 `scripts/run_final_training.sh`，排名导出入口是 `scripts/run_final_inference.sh`。GPU 基准环境为单张 RTX 4090 24 GB。完整测试命令 `pytest -q` 当前通过 71 项测试。

## 数据处理

最终训练表为 `data/processed/benchmark_team_routed_v6_global_family.csv`。它由非 VHH 原始序列整理而来，保留原始来源、endpoint、标签方向、可信等级、comparison group、任务路由及 family split。最终主路线只读取 `task_route=alphaseq_rank`。

外层验证按生物学唯一重轻链对去重后为 94,848 条；训练—验证精确重轻链交集为 0。内层 holdout 由 `bioos_benchmark.inner_family_split` 从外层训练 family 中重新分配，外层验证全部标记为 `excluded`。

## 训练顺序

1. 安装 `requirements-lock.txt` 环境并确认 CUDA；
2. 运行数据治理脚本得到 v6 最终表；
3. 用固定 ESM-2 snapshot 生成重链/轻链缓存；
4. 在训练 embedding 上构建 K=8 父本簇；
5. 训练 Stage 17 稳定位置卷积组件；
6. 训练 K8 绝对父本模型；
7. 训练共识母本差分模型；
8. 按固定权重做百分位秩融合；
9. 导出非 VHH 去重重轻链、分数和 Rank。

核心命令：

```bash
bash scripts/run_final_training.sh \
  data/processed/benchmark_team_routed_v6_global_family.csv \
  artifacts/final/esm150_embeddings.pt
```

训练脚本不会自动修改预注册权重。Stage 17 的完整历史组件与命令参数保存在对应 checkpoint `metrics.json`；正式融合由 `scripts/build_stage21_preregistered_outer_ensemble.py` 完成。

## 超参数

| 参数 | 正式值 |
|---|---:|
| ESM backbone | ESM-2 t30 150M |
| ESM hidden size | 640 |
| 父本簇数/组 | 8 |
| residue embedding | 16 |
| Conv channels | 48 |
| Conv kernels | 3, 5 |
| MLP hidden | 384, 96 |
| dropout | 0.2 |
| batch size | 2048 |
| epochs upper bound | 30 |
| learning rate | 3e-4 |
| weight decay | 2e-4 |
| rank loss weight | 0.04 |
| early-stop patience | 15 |

超参数和融合权重在训练内部 holdout 选择；外层验证不用于再次调权。

## 收敛与选择

每轮保存训练总损失、学习率与验证 Spearman。训练损失继续下降不代表排序改善，因此 checkpoint 按最高验证 Spearman 保存，连续 15 轮不提升提前停止。正式外层共识差分模型最佳 Spearman 为 0.443089；K8 绝对父本单模为 0.452528。

## 推理与抗体序列导出

对赛事标准候选集运行固定组件推理并得到 `record_id,prediction` 后：

```bash
bash scripts/run_final_inference.sh \
  data/processed/benchmark_team_routed_v6_global_family.csv \
  artifacts/final/preregistered_outer_parent_delta_ensemble.csv \
  deliverables/antibody_sequences.csv.gz
```

输出字段：`sequence_id,rank,score,heavy,light,source_count`。`sequence_id` 是重轻链连接后 SHA-256 的前 20 位，便于确定性去重；Rank 以 score 降序、sequence_id 破同分。轻链为空的 VHH 被显式排除。

注意：当前保存的 train-only 聚类 artifact 主要覆盖标准候选集合。任意全新抗体应先运行 ESM 编码并分配到训练中心；不能把未知 pair 强行映射成已有 ID。

## 测试结果

```bash
pytest -q
# 71 passed
```

测试覆盖标签方向、数据拆分、身份泄漏、family 分割、模型张量、集成、bootstrap、父本聚类、内层切分与局部参考的训练自排除/验证 train-only 约束。

## 计算资源

- GPU：NVIDIA GeForce RTX 4090，24,564 MiB；
- Driver：550.78；
- Python：3.11.7；
- PyTorch：2.2.2；
- ESM embedding：154,451 条唯一序列，640 维 float16，约 216 MB；
- 神经 checkpoint：单模型约 17.5 MB；
- 局部参考矩阵乘法和神经训练使用 CUDA；CSV 整理与 KMeans 主要使用 CPU/RAM。

## 已知不足

landscape1 混合多个父本且重复测量噪声高，Spearman 0.275867；landscape2 为 0.656478。Stage 21 相对 Stage 18 增益仅 0.000310，配对 bootstrap 胜率 97.2%，但 95% 区间下界略低于 0，应视为小幅谨慎晋升。
