# 公共数据与接口契约

> 负责人：两位同学共同确认  
> 状态：接口设计完成，代码实现待开始  
> 目的：让两条模型路线可以真正并行，而不依赖对方的内部代码

## 1. 规范化样本接口

两条路线共同读取 `canonical_dataset.csv` 或同字段的 Parquet 文件。最小必需字段如下：

| 字段 | 类型 | 含义 |
|---|---|---|
| `record_id` | string | 全局稳定样本 ID |
| `heavy` | string | VH 或 VHH 氨基酸序列 |
| `light` | string | VL 序列；VHH 时为空字符串 |
| `antigen_seq` | string | 抗原序列；未知时为空字符串 |
| `target_id` | string | 靶点或抗原簇标识，只用于分组 |
| `source_group` | string | 论文/来源组，只用于切分和评价 |
| `assay_family` | string | `kd`、`ic50`、`ec50`、`binding` 等 |
| `canonical_label` | float | 已统一方向的监督值，越大越好 |
| `within_group_rank` | float | 同实验上下文内的 0～1 百分位 |
| `label_quality` | float | 0～1 标签可信度 |
| `affinity_grade` | string | 人工认证的 A～D/NA 亲和力监督等级 |
| `training_head` | string | `affinity_kd`、`neutralization_ic50` 等独立任务头 |
| `certification_version` | string | 标签认证规则版本，便于追踪结果 |
| `is_censored` | int | 是否为测量上/下限 |
| `split` | string | `train`、`validation` 或 `test` |
| `split_group` | string | 防泄漏分组标识 |

模型不得依赖 CSV 行号。输出和输入必须通过 `record_id` 对齐。

主亲和力模型只读取 `training_head=affinity_kd` 且 `primary_affinity_weight>0` 的记录。IC50、EC50、二分类、OVA 风险、ADCC 和未拆分的混合终点不能仅翻转正负号后并入同一回归头。

## 2. Python 数据对象

计划在 `src/bioos_benchmark/contracts.py` 中提供：

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RankingRecord:
    record_id: str
    heavy: str
    light: str
    antigen_seq: str
    target_id: str
    source_group: str
    assay_family: str
    canonical_label: float | None
    within_group_rank: float | None
    label_quality: float
    is_censored: bool
    split: str
    split_group: str
```

公共加载接口：

```python
def load_ranking_records(
    path: str,
    split: str | None = None,
) -> list[RankingRecord]:
    """按 record_id 稳定排序并加载样本。"""
```

## 3. 模型统一接口

不论内部是深度网络还是数学模型，都实现以下协议：

```python
from typing import Protocol, Sequence

class AffinityRanker(Protocol):
    def fit(
        self,
        records: Sequence[RankingRecord],
        *,
        validation_records: Sequence[RankingRecord] | None = None,
    ) -> "AffinityRanker":
        ...

    def predict_score(
        self,
        records: Sequence[RankingRecord],
    ) -> list[float]:
        """返回连续分数；数值越大表示预测亲和力越强。"""

    def save(self, output_dir: str) -> None:
        ...
```

统一加载接口：

```python
def load_ranker(model_dir: str) -> AffinityRanker:
    """从模型目录读取配置与权重。"""
```

## 4. 预测文件接口

每条路线必须输出：

```csv
record_id,split,source_group,target_id,y_true,score,model_id
```

约束：

- `score` 越大越好；
- `record_id` 唯一；
- 不允许缺失或无穷分数；
- 测试集没有标签时，`y_true` 留空；
- `model_id` 必须包含路线、配置和随机种子。

示例：

```csv
record_id,split,source_group,target_id,y_true,score,model_id
rec_001,validation,paper_03,target_a,0.82,1.734,deep_v1_seed42
rec_002,validation,paper_03,target_a,0.31,-0.408,deep_v1_seed42
```

## 5. 最终提交接口

```python
def scores_to_submission(
    records: list[RankingRecord],
    scores: list[float],
    output_path: str,
) -> None:
    """按 score 降序生成连续且唯一的 Rank。"""
```

输出字段：

```csv
VH/VHH,VL,Rank
```

规则：

- `Rank=1` 表示预测亲和力最高；
- Rank 必须是从 1 开始的连续整数；
- VHH 的 `VL` 必须为空；
- 序列必须与输入逐字符一致；
- 分数相同时用 `record_id` 做稳定次序，保证复现。

## 6. 统一命令行约定

```bash
bioos-train-deep --config configs/deep_ranker.yaml
bioos-predict-deep --model-dir artifacts/deep/fold_0 --input data/test.csv --output predictions/deep.csv

bioos-train-math --config configs/math_ranker.yaml
bioos-predict-math --model-dir artifacts/math/fold_0 --input data/test.csv --output predictions/math.csv

bioos-evaluate --truth data/validation.csv --predictions predictions/deep.csv
bioos-ensemble --inputs predictions/deep.csv predictions/math.csv --output predictions/ensemble.csv
bioos-submit --input data/test.csv --predictions predictions/ensemble.csv --output submission.csv
```

## 7. 错误约定

以下情况必须直接报错，不允许静默跳过：

- `record_id` 重复；
- 重链为空或含非法字符；
- 预测文件丢失输入样本；
- `score` 含 NaN/Inf；
- 训练集和验证集存在相同 `split_group`；
- 标签方向未登记；
- VHH 被错误填入 light；
- 最终 Rank 不连续或方向相反。
