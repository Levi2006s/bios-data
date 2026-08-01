# B2：可解释数学排序模型

> 负责人：数学同学  
> 状态：已实现并验证  
> 实现位置：`src/bioos_benchmark/ranking/math_ranker.py`  
> 测试位置：`tests/test_math_ranker.py`  
> 前置依赖：B1 preference pairs、公共接口契约

## 模块简介

这条路线不依赖复杂端到端神经网络，而是把“谁优于谁”作为主要监督。它既是一条可独立参赛的路线，也是检查深度模型是否真的学到有效规律的重要对照。

推荐从简单到复杂实现两级模型：

1. `Math-v0`：质量加权 Bradley–Terry / pairwise logistic；
2. `Math-v1`：带样本特征的质量加权 pairwise logistic 排序模型。

当前 v1 选择 pairwise logistic，而不是立即加入额外的 LightGBM/XGBoost 依赖。它直接优化 pair 顺序、支持稀疏 k-mer 特征、容易解释，也能在当前环境中开箱复现。后续可把 LambdaRank 作为同接口的可选增强。

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

实现文件：`src/bioos_benchmark/ranking/math_ranker.py`

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

class FeaturePairwiseRanker:
    def fit(
        self,
        records: list[dict[str, str]],
        pairs: list["PreferencePair"],
    ) -> "FeaturePairwiseRanker":
        ...

    def predict_score(
        self,
        records: list[dict[str, str]],
    ) -> "numpy.ndarray":
        ...

    def pair_accuracy(
        self,
        records: list[dict[str, str]],
        pairs: list["PreferencePair"],
    ) -> float:
        ...

    def save(self, output_dir: Path) -> None:
        ...

    @classmethod
    def load(cls, model_dir: Path) -> "FeaturePairwiseRanker":
        ...
```

## 命令行接口

```bash
bioos-train-math \
  --input data/processed/benchmark_with_split.csv \
  --pairs data/processed/pairs_train.csv \
  --artifact-dir artifacts/math/fold_0 \
  --seed 42

bioos-predict-math \
  --model-dir artifacts/math/fold_0 \
  --input data/processed/canonical_dataset.csv \
  --split validation \
  --output predictions/math_fold_0.csv
```

## 训练函数接口

```python
def train_math_ranker(
    input_path: Path,
    pairs_path: Path,
    artifact_dir: Path,
    *,
    train_split: str = "train",
    validation_split: str = "validation",
    n_features: int = 2**16,
    seed: int = 42,
    alpha: float = 1e-5,
    max_iter: int = 2000,
) -> dict[str, object]:
    ...

def predict_math_ranker(
    model_dir: Path,
    input_path: Path,
    output_path: Path,
    *,
    split: str | None = None,
) -> int:
    ...
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

当前版本已输出 `train_pair_accuracy`、验证集基础指标和公共契约预测文件。更完整的 per-source 指标与置信区间由 B3 统一计算。

## 模型产物

```text
artifacts/math/fold_0/
├── model.joblib
├── config.json
├── metrics.json
└── predictions_validation.csv
```

分数方向固定为“越大越好”。验证样本少于 3 条时，无法定义的相关系数写为 JSON `null`，不会写出非法 `NaN`。

## 验收结果

- Math-v0 在合成偏好数据上恢复正确次序；
- 质量为 0 的 pair 不影响参数；
- 训练只使用 train split；
- Math-v1 至少优于常数、长度模型和 metadata-only 负对照；
- 输出和深度路线使用同样的 `record_id + score` 契约；
- 模型、特征字典和配置可以保存并重新加载。

实际测试：

```bash
$env:PYTHONPATH="src"
python -m pytest -q tests/test_math_preferences.py tests/test_math_ranker.py
```

```text
8 passed in 1.23s
```

已验证：

- Bradley–Terry 恢复合成数据的正确次序；
- pairwise 模型输出有限连续分数；
- 训练 pair 加权准确率可计算；
- 模型保存与加载前后的预测一致；
- 训练函数生成模型、配置、指标和验证预测；
- 推理输出符合公共 `record_id + score` 契约；
- 不可计算指标安全写成 `null`。

## 变更记录

| 日期 | 版本 | 修改 |
|---|---|---|
| 2026-07-26 | v0.1 | 实现 Bradley–Terry、序列特征 pairwise ranker、训练/推理 CLI 和测试 |
