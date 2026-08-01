# 06 - 完全重复序列和跨文件重复追踪

## 模块简介

本模块把“同一重链+轻链组合”定义为精确抗体身份。它只统计和追踪重复，不直接删除，因为同一抗体在不同抗原、实验条件或重复测量中的记录仍可能有价值。

## 全量结果

| 指标 | 数量 |
|---|---:|
| 通过标签与重链检查的监督记录 | 2,009,775 |
| 精确唯一的重链+轻链组合 | 277,515 |
| 出现至少两次的组合 | 240,779 |
| 第一条之后的重复记录 | 1,732,260 |
| 跨论文来源的重复记录 | 438,306 |
| 启发式抗体家族桶 | 82,967 |
| 唯一合法抗原序列 | 2,609 |

重复率很高并不一定代表数据坏了。例如 AVIDa-hIL6 会让同一个 VHH 与多个 IL-6 变体配对；来源 3 还包含 assay/replicate 记录。

最重要的重复关系：

- 来源 6 的 352,139 条有标签记录全部也出现在来源 3 中；
- AbRank 有 166,994 条重复抗体记录，其中 86,153 条与其他来源重合；
- AVIDa-hIL6 内部有 535,292 条“同抗体、不同记录”的重复；
- 来源 3 两个文件内部合计超过 59 万条重复记录。

因此不能先随机按行切分再训练，否则同一抗体很容易同时出现在训练集和测试集，指标会虚高。

## 重复定义

- `exact antibody`：标准化后的 `heavy + light` 完全一致；
- `heuristic family`：重轻链长度桶、两端框架锚点和 CDRH3/重链尾部签名一致；
- `exact antigen`：合法抗原序列完全一致。

启发式 family 只用于快速分组，不等价于正式的 MMseqs2/CD-HIT 序列一致性聚类。

## 接口

```python
from bioos_benchmark.curation import curate_audit

summary = curate_audit(data_root, registry_path, audit_csv, output_dir)
print(summary["unique_exact_antibodies"])
```

命令行：

```powershell
python -m bioos_benchmark.curation `
  --data-root "<原始数据目录>" `
  --registry configs/label_registry.csv `
  --audit data/processed/audit.csv `
  --output-dir data/processed/curation
```

