# 06 - 完全重复序列和跨文件重复追踪

## 模块简介

本模块把“同一重链+轻链组合”定义为精确抗体身份。它只统计和追踪重复，不直接删除，因为同一抗体在不同抗原、实验条件或重复测量中的记录仍可能有价值。

## 全量结果

| 指标 | 数量 |
|---|---:|
| 修订后通过标签与重链检查的监督记录 | 1,840,537 |
| 其中主 KD 亲和力任务记录 | 1,186,857 |
| 精确唯一的重链+轻链组合 | 275,272 |
| 出现至少两次的组合 | 239,402 |
| 第一条之后的重复记录 | 1,565,265 |
| 跨论文来源的重复记录 | 352,151 |
| 启发式抗体家族桶 | 80,792 |
| 唯一合法抗原序列 | 10 |

这里的下降主要因为未按 measurement type 拆分的 AbRank 被转为待处理数据，不再进入监督统计；它的原始记录没有被删除。

重复率很高并不一定代表数据坏了。例如 AVIDa-hIL6 会让同一个 VHH 与多个 IL-6 变体配对；来源 3 还包含 assay/replicate 记录。

最重要的重复关系：

- 来源 6 的 352,139 条有标签记录全部也出现在来源 3 中；
- AbRank 的历史重复统计仍保留在旧审计结果中，但修订后不进入监督切分；
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
