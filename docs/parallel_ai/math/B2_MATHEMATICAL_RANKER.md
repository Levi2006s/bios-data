# B2：可解释数学排序模型

> 负责人：数学同学  
> 状态：模块设计完成，代码待实现  
> 前置依赖：B1 preference pairs、公共接口契约

## 模块简介

这条路线不依赖复杂端到端神经网络，而是把“谁优于谁”作为主要监督。它既是一条可独立参赛的路线，也是检查深度模型是否真的学到有效规律的重要对照。

推荐从简单到复杂实现两级模型：

1. `Math-v0`：质量加权 Bradley–Terry / pairwise logistic；
2. `Math-v1`：带样本特征的 LambdaRank 或梯度提升排序模型。

## Math-v0：Bradley–Terry 基线

设样本潜在强度为 \(s_i\)，则：

```text
P(i 优于 j) = sigmoid(s_i - s_j)
```

最小化质量加权负对数似然，并加入正则项。这个模型可以用于：

- 检查 preference graph 是否自洽；
- 给训练样本生成平滑潜在分数；
- 发现强循环矛盾和异常标签组。

## Math-v1：特征排序模型

输入特征可包括：

- 当前仓库已有的序列长度、氨基酸组成、疏水性、电荷、半胱氨酸等；
- k-mer 特征；
- A1 生成的冻结 PLM embedding（可选，不应成为阻塞项）；
- 是否缺失 light/antigen 的 mask；
- assay 类型的低维 one-hot。

不得使用论文 ID、文件名、PDB ID 等来源捷径。

## Python 接口

计划文件：`src/bioos_benchmark/ranking/math_ranker.py`

```python
class BradleyTerryRanker:
    def fit(
        self,
        pairs: list["PreferencePair"],
        record_ids: list[str],
    ) -> "BradleyTerryRanker":
        ...

    def predict_score(self, record_ids: list[str]) -> list[float]:
        """返回潜在强度；越大越好。"""

class FeatureRanker:
    def fit(
        self,
        features,
        labels,
        group_sizes,
        sample_weight=None,
    ) -> "FeatureRanker":
        ...

    def predict_score(self, features) -> list[float]:
        ...

def build_math_ranker(config: dict):
    """根据 model_type 创建可解释排序器。"""
```

## 命令行接口

```bash
bioos-train-math \
  --config configs/math_ranker.yaml \
  --fold 0 \
  --seed 42

bioos-predict-math \
  --model-dir artifacts/math/fold_0 \
  --input data/processed/canonical_dataset.csv \
  --output predictions/math_fold_0.csv
```

## 配置示例

```yaml
model_id: math_v1
model_type: lambda_rank
feature_sets:
  - physicochemical
  - kmer
use_plm_embedding: false
quality_weighted: true
source_balanced: true
seed: 42
```

## 诊断输出

除公共预测文件外，至少输出：

```text
pair_accuracy
preference_cycle_rate
score_distribution
feature_importance
per_source_spearman
```

## 验收标准

- Math-v0 在合成偏好数据上恢复正确次序；
- 质量为 0 的 pair 不影响参数；
- 训练只使用 train split；
- Math-v1 至少优于常数、长度模型和 metadata-only 负对照；
- 输出和深度路线使用同样的 `record_id + score` 契约；
- 模型、特征字典和配置可以保存并重新加载。
