# B1：偏好关系与标签质量模块

> 负责人：数学同学  
> 状态：模块设计完成，代码待实现  
> 目标：把异质实验标签转换成可信的相对大小关系

## 模块简介

Spearman 关心的是排序，不要求模型精确预测 pKd。数学路线首先把可比较样本转换成：

```text
样本 i 比样本 j 更好
```

不能比较的样本不强行组成 pair。例如 KD 与 IC50 不直接比较，不同靶点不直接比较，两个相同或都被截断的标签不建立强顺序。

## 数学定义

在同一比较组 \(g\) 内，若统一方向后的标签满足：

```text
y_i - y_j > margin_g
```

则定义：

```text
preference(i, j) = +1
```

pair 权重建议为：

```text
w_ij =
quality_i × quality_j
× gap_weight(|y_i - y_j|)
× censor_weight
× conflict_weight
```

权重范围限制在 `[0, 1]`。

## 比较组

默认比较组：

```text
paper_group + target_id + assay_family + assay_format
```

若字段缺失，应使用 label registry 给出的逐文件规则，不允许自动跨 assay 合并。

## Python 接口

计划文件：`src/bioos_benchmark/ranking/preferences.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PreferencePair:
    left_record_id: str
    right_record_id: str
    preference: int
    pair_weight: float
    comparison_group: str
    reason: str

def build_preference_pairs(
    records: list["RankingRecord"],
    *,
    min_gap: float = 0.0,
    max_pairs_per_group: int = 100_000,
    seed: int = 42,
) -> list[PreferencePair]:
    """构造可复现、质量加权的 pair。"""

def validate_preference_pairs(
    pairs: list[PreferencePair],
    records: list["RankingRecord"],
) -> dict[str, object]:
    """检查方向、跨 split、并列、截断和重复冲突。"""
```

## 命令行接口

```bash
bioos-build-pairs \
  --input data/processed/canonical_dataset.csv \
  --split train \
  --output data/processed/pairs_train.csv \
  --max-pairs-per-group 100000 \
  --seed 42
```

输出字段：

```csv
left_record_id,right_record_id,preference,pair_weight,comparison_group,reason
```

## 抽样策略

大组不能生成全部 \(O(n^2)\) pair。建议：

- 按标签间隔分层抽样；
- 每个样本限制最大 pair 数；
- 小来源适当过采样；
- 极大来源限制上限；
- 固定随机种子；
- 保存每类 pair 的数量报告。

## 验收标准

- pair 两端一定处于同一 split；
- pair 不跨不兼容 assay；
- 相同标签不生成强偏好；
- 两个同方向截断样本不生成强偏好；
- 交换左右时 preference 符号相反；
- 标签打乱后模型验证 Spearman 接近 0；
- 输出哈希和统计摘要可复现。
