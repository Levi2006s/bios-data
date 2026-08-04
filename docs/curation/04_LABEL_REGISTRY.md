# 04 - 标签方向、单位和可信等级覆盖表

## 模块简介

本模块把人工复核结论变成程序可读的配置，防止代码再次只看 `fitness` 这个模糊字段名进行猜测。

## 覆盖结果

| 项目 | 数量 |
|---|---:|
| 已登记文件 | 83 |
| 覆盖率 | 100% |
| 方向 +1 | 49 |
| 方向 -1 | 33 |
| 无监督方向 | 1 |
| Gold | 71 |
| Silver | 5 |
| Weak | 3 |
| Auxiliary | 4 |

三份二分类 binding 数据保留为辅助分类监督，但明确排除在主亲和力排序监督之外。

按记录统计：

| 等级 | 原始行 | 通过人工规则的监督行 | 缺失/非法标签 |
|---|---:|---:|---:|
| Gold | 88,155 | 88,152 | 0，另有 3 条超范围 |
| Silver | 342,800 | 169,682 | 173,118 |
| Weak | 3,515,760 | 1,099,640 | 2,416,120 |
| Auxiliary | 657,554 | 0 | 不适用 |

## 登记表字段

`label_registry.csv` 为每个文件记录：论文、年份、原始标签列、指标、单位、变换、方向、标签来源、等级、合理范围、截断策略、证据、置信度和备注。

程序遇到未登记文件会报错，而不是继续自动猜测。KD=0、非有限数值或明显超出合理范围的值会进入隔离统计，不会被静默裁剪。

## 接口

```python
from pathlib import Path
from bioos_benchmark.curation import load_registry, label_is_valid

registry = load_registry(Path("configs/label_registry.csv"))
entry = registry["初赛-序列数据/4/AbRank_dataset.csv"]
assert entry["direction"] == "-1"
assert label_is_valid(2.9112, entry)
```

生成兼容旧预处理代码的方向覆盖表：

```powershell
python scripts/build_label_registry.py `
  --output configs/label_registry.csv `
  --overrides configs/direction_overrides.csv
```
