# 07 - 论文组、抗体簇、抗原簇和时间拆分

## 模块简介

本模块同时生成四类拆分，便于判断模型是在记忆已有抗体，还是能泛化到新论文、新抗体或未来数据。

| 拆分 | 做法 | 主要用途 |
|---|---|---|
| 论文组拆分 | 同一篇论文的所有文件进入同一集合 | 避免实验批次泄漏 |
| 抗体安全拆分 | 先把存在精确重复抗体的来源合并成连通分量 | 避免同抗体跨集合 |
| 抗体家族拆分 | 使用可复现的启发式 family 桶连接来源 | 更严格的近似家族隔离 |
| 抗原拆分 | 相同合法抗原序列的来源保持在一起 | 测试新抗原泛化 |
| 时间拆分 | 2022 及以前训练，2023 验证，2024 以后测试 | 模拟未来数据 |

## 分组结果

- 论文组拆分：15 个来源组训练、3 个验证、4 个测试；
- 精确抗体重复把 22 个来源连接成 15 个连通分量；
- 抗体安全拆分：17 个来源组训练、2 个验证、3 个测试；
- 时间拆分：8 个来源组训练、6 个验证、8 个测试。

标准化样例的记录分布：

| 拆分 | 训练 | 验证 | 测试 |
|---|---:|---:|---:|
| 论文组 | 3,144 | 220 | 600 |
| 精确抗体安全 | 3,344 | 120 | 500 |
| 时间 | 1,427 | 882 | 1,655 |

建议正式 Benchmark 至少同时报告“论文组拆分”和“时间拆分”；抗体安全拆分用于检查记忆泄漏。抗原序列只有约 3.27% 的原始记录具备，因此抗原拆分只能作为较小的严格子集，不能代表全部数据。

## 输出与接口

- 分组规则：`data/processed/curation/split_group_manifest.csv`
- 已附加拆分字段的样例：`data/processed/curation/curated_sample_with_splits.csv`

```python
from pathlib import Path
from bioos_benchmark.apply_splits import apply_split_manifest

apply_split_manifest(
    Path("data/processed/curation/curated_sample.csv"),
    Path("data/processed/curation/split_group_manifest.csv"),
    Path("data/processed/curation/curated_sample_with_splits.csv"),
)
```

```powershell
python -m bioos_benchmark.apply_splits `
  --input data/processed/curation/curated_sample.csv `
  --manifest data/processed/curation/split_group_manifest.csv `
  --output data/processed/curation/curated_sample_with_splits.csv
```
