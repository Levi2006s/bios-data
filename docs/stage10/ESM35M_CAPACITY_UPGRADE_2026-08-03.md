# 阶段 10：ESM-2 35M 容量升级

日期：2026-08-03

## 模型身份

- Hugging Face repo：`facebook/esm2_t12_35M_UR50D`
- 固定 revision：`6fbf070e65b0b7291e7bbcd451118c216cff79d8`
- safetensors SHA-256：`e35647818e0e064351d4531ed480d225a002567b4b2b93ad3a9246d753150fc0`
- Transformer 层数：12
- hidden size：480
- 唯一序列：70,902
- pooling：`attention_mean`，与阶段 6 一致
- 硬件：NVIDIA GeForce RTX 4090

## 单模型结果

保持 v3 数据、抽样种子、framework-family 划分和下游交互头逻辑一致。

| 模型/设置 | Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: |
| ESM-2 8M，lr=3e-4 | **0.445573** | **0.52679** | **2.4340** |
| ESM-2 35M，lr=3e-4 | 0.359435 | 0.49119 | 1.7472 |
| ESM-2 35M，lr=1e-4，seed 20260803 | 0.390023 | 0.49588 | 2.0484 |
| ESM-2 35M，lr=1e-4，seed 20260804 | 0.384215 | 0.49424 | 2.0846 |

更大编码器的单模型并未超过 8M。低学习率能稳定改善 35M，说明高维表征的下游头更易优化过快，但当前数据/头结构下仍不占优。

## 融合结果

35M seed 20260803 与 8M 的预测秩相关约 0.659，提供了可用多样性。第二个 35M 种子在粗网格最优组合中的权重为 0，故排除。

### 高分候选

- ESM-8M：50%
- CNN seed 20260803：15%
- CNN seed 20260804：15%
- ESM-35M seed 20260803：20%

指标：

- Spearman：**0.460684**
- Pearson：0.519959
- Top-10 enrichment：2.783465

相比阶段 6 稳定基线 `0.457070`，Spearman 提升 `+0.003614`。2.5% 精细网格最高为 0.460773，但为减少同验证集调权偏差，选择较简单的 5% 权重候选。

### 稳定性

精细候选相对阶段 6 的 10,000 次来源组配对 bootstrap：

- 点差：+0.003703
- 候选胜出概率：83.03%
- 95% 区间：[-0.06551, 0.06323]

证据支持“可能提高排行榜点分”，尚不足以证明跨来源稳定提升。因此：

- `0.460684` 是当前高分提交候选；
- `0.457070` 继续作为稳定基线；
- 在新增多折或隐藏测试结果前，不宣称 35M 已稳定替代阶段 6。

## 产物

- embeddings：`artifacts/stage10/esm2_t12_35m_embeddings.pt`
- 最佳 35M 头：`artifacts/stage10/esm2_t12_35m_head_lr1e4_seed_20260803/`
- 高分融合：`artifacts/stage10/high_score_candidate_ensemble.csv`
