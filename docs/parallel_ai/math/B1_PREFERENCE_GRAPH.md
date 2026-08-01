# B1：偏好关系与标签质量模块

> 负责人：数学同学  
> 状态：已实现并验证  
> 实现位置：`src/bioos_benchmark/ranking/preferences.py`  
> 测试位置：`tests/test_math_preferences.py`  
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

实现文件：`src/bioos_benchmark/ranking/preferences.py`

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
    records: list[dict[str, object]],
    *,
    min_gap: float = 0.0,
    max_pairs_per_group: int = 100_000,
    max_pairs_total: int = 1_000_000,
    seed: int = 42,
    group_fields: list[str] | None = None,
) -> list[PreferencePair]:
    """构造可复现、质量加权的 pair。"""

def validate_preference_pairs(
    pairs: list[PreferencePair],
    records: list[dict[str, object]],
    *,
    group_fields: list[str] | None = None,
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
  --max-pairs-total 1000000 \
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
- 全部来源合计默认最多 1,000,000 个 pair；
- 固定随机种子；
- 保存每类 pair 的数量报告。

## 当前实现的字段兼容

标签按以下优先级读取：

```text
canonical_label
→ within_group_rank
→ score
→ raw_label × direction
```

比较组优先使用显式 `comparison_group`。没有该字段时，自动使用现有数据中的 `source_file、antigen_id`，并兼容未来的 `paper_group、target_id、assay_family、assay_format`。

缺少 `label_quality、is_censored、replicate_conflict` 时分别采用安全默认值 `1、False、0`，因此当前 `benchmark_with_split.csv` 可以直接调用。

## 验收结果

- pair 两端一定处于同一 split；
- pair 不跨不兼容 assay；
- 相同标签不生成强偏好；
- 两个同方向截断样本不生成强偏好；
- 交换左右时 preference 符号相反；
- 标签打乱后模型验证 Spearman 接近 0；
- 输出哈希和统计摘要可复现。

实际测试：

```bash
$env:PYTHONPATH="src"
python -m pytest -q tests/test_math_preferences.py
```

```text
5 passed in 0.06s
```

已覆盖：

- 固定种子下结果可复现；
- 并列标签不生成 pair；
- 双截断样本不生成 pair；
- 跨 split 不生成 pair；
- `raw_label × direction` 回退方向正确；
- 全局 pair 上限在来源之间均衡分配；
- 命令行能够写出 pair CSV 和 summary JSON。

## 输出文件

```text
pairs.csv
pairs.summary.json
```

summary 包含 pair 数量、比较组数量、权重范围、按组计数、按降权原因计数和校验错误。

## 变更记录

| 日期 | 版本 | 修改 |
|---|---|---|
| 2026-07-26 | v0.1 | 实现偏好 pair、质量权重、校验、CLI 和测试 |
