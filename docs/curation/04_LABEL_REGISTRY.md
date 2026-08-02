# 04 - 标签方向、单位和可信等级覆盖表

## 模块简介

本模块把人工复核结论变成程序可读的配置，防止代码再次只看 `fitness` 这个模糊字段名进行猜测。2026-08-03 的修订版进一步区分“实验终点可信度”和“作为 KD 亲和力监督的可信度”，详细变更见 `08_LABEL_CERTIFICATION_REVISION_2026-08-03.md`。

## 覆盖结果

| 项目 | 数量 |
|---|---:|
| 已登记文件 | 83 |
| 覆盖率 | 100% |
| 方向 +1 | 47 |
| 方向 -1 | 34 |
| 无全局方向/无监督方向 | 2 |
| Gold | 74 |
| Silver | 8 |
| Auxiliary | 1 |

按记录统计：

| 等级 | 原始行 | 通过人工规则的监督行 | 缺失/非法标签 |
|---|---:|---:|---:|
| Gold | 740,456 | 740,453 | 0，另有 3 条超范围 |
| Silver | 3,858,560 | 1,100,084 | 2,416,120；另有 342,356 条待拆分 AbRank |
| Auxiliary | 5,253 | 0 | 不适用 |

## 登记表字段

`label_registry.csv` 为每个文件记录：论文、年份、原始标签列、指标、单位、变换、方向、标签来源、等级、合理范围、截断策略、证据、置信度和备注。修订版还增加 `endpoint_grade`、`affinity_grade`、`training_head`、`primary_affinity_weight`、可比范围和认证意见。

程序遇到未登记文件会报错，而不是继续自动猜测。KD=0、非有限数值或明显超出合理范围的值会进入隔离统计，不会被静默裁剪。

## 接口

```python
from pathlib import Path
from bioos_benchmark.curation import load_registry, label_is_valid

registry = load_registry(Path("configs/label_registry.csv"))
entry = registry["初赛-序列数据/4/AbRank_dataset.csv"]
assert entry["direction"] == "0"
assert entry["training_head"] == "mixed_endpoint_split_required"
assert entry["supervised_use"] == "conditional"
```

生成兼容旧预处理代码的方向覆盖表：

```powershell
python scripts/build_label_registry.py `
  --audit data/processed/audit.csv `
  --certification configs/label_certification_revision.csv `
  --output configs/label_registry.csv `
  --overrides configs/direction_overrides.csv
```
