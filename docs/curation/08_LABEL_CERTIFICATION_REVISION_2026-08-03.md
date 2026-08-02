# 抗体标签可信度认证表修订落地说明

> 日期：2026-08-03  
> 输入：`抗体标签可信度认证表_修订版.docx`  
> 状态：83/83 个文件已匹配，代码、配置和数学基线已复核

## 1. 模块简介

这个模块把医学生审核后的 Word 表格变成程序能直接读取的规则。它解决的不只是“数字越大还是越小”，还把以下问题分开记录：

- 实验本身是否可信；
- 这个结果能不能代表真正的抗体亲和力；
- 它应该进入 KD、IC50、EC50、二分类还是安全性风险任务；
- 两个样本是否允许互相比较；
- 进入主亲和力模型时应该使用多大权重。

原始 CSV 没有被改名或改写。Word 表中 82 个文件名直接匹配；`makowski2022cooptimization_iso_ant.csv` 与原始文件 `makowksi2022cooptimization_iso_ant.csv` 的差异被记录为一个文件名别名。

## 2. 修订后的等级

Word 表只定义 A、B、C、D 和中间等级，没有指定精确数值。为了让训练代码可复现，本项目采用公开、可调的线性权重映射：

| 亲和力等级 | 工程权重 |
|---|---:|
| A | 1.000 |
| A/B | 0.875 |
| B | 0.750 |
| B/C | 0.625 |
| C | 0.500 |
| C/D | 0.250 |
| D、NA | 0.000 |

`grade_weight` 是等级对应的通用权重；`primary_affinity_weight` 是当前 KD 主任务真正使用的权重。后者对 IC50、EC50、二分类、OVA 风险、ADCC 和尚未拆分的 AbRank 设为 0，防止它们被混入一个 KD 回归或排序头。

83 个文件的亲和力等级分布为：A 10 个、A/B 37 个、B 6 个、B/C 15 个、C 7 个、C/D 1 个、D 6 个、NA 1 个。

## 3. 任务拆分结果

| `training_head` | 文件数 | 用途 |
|---|---:|---|
| `affinity_kd` | 58 | KD、pKD、SPR 或 AlphaSeq 校准亲和力 |
| `binding_ec50` | 10 | 独立 EC50 预测头 |
| `neutralization_ic50` | 5 | 独立中和/抑制 IC50 预测头 |
| `binding_classification` | 3 | bind/no-bind 二分类 |
| `relative_target_binding` | 2 | 目标抗原相对结合信号 |
| `developability_ova_risk` | 2 | OVA 非特异结合风险，越小越好 |
| `adcc_function` | 1 | ADCC 复合功能终点 |
| `mixed_endpoint_split_required` | 1 | AbRank，先按 measurement type 拆分 |
| `unsupervised` | 1 | 仅用于预训练、去重或表征 |

## 4. 已执行的关键修正

1. Makowski 的两个 OVA 文件改为开发价值“越小越好”，注册表方向为 `-1`，但只进入 OVA 风险头。
2. Li/Engelhart 的 AlphaSeq 标签改为“实验衍生、模型校准”，不再写成纯计算伪标签；亲和力等级 B/C，主任务权重 0.625。
3. AbRank 不再使用全局统一方向；注册表方向为 `0`、`supervised_use=conditional`，必须按 `measurement_type` 拆分后才能训练。
4. KD/pKD、IC50、EC50、相对结合、二分类、ADCC 和 OVA 风险被分到不同训练头。
5. Fab、IgG、scFv、VHH 的分子格式信息继续保留；当前偏好对按来源文件、抗原和检测类型分组，不跨文件强行比较。

## 5. 修订后数学基线复核

输入仍是 3,964 条审计样本。主 KD 路线保留 2,565 条：训练 1,945、验证 120、测试 500；另外 1,399 条按独立任务头隔离。训练集生成 45,195 个偏好对，58 个可比较实验组。

| 模型 | 训练 pair accuracy | 验证 Spearman | Top-10% 富集 | Spearman 95% CI |
|---|---:|---:|---:|---|
| seed 42 | 0.8035 | -0.0655 | 1.6667 | [-0.1153, 0.7729] |
| seed 43 | 0.8046 | -0.0659 | 1.6667 | [-0.1159, 0.7729] |
| 50/50 集成 | 不适用 | 0.0466 | 0.0000 | [-0.1153, 0.7729] |

验证集只有 120 条、2 个独立来源，置信区间很宽。因此这些数值只说明代码能够按新规则运行，不能说明简单模型已经具备可靠的跨来源泛化能力。

## 6. 可调用接口

### 6.1 从 Word 表重新生成机器配置

```powershell
python scripts/import_label_certification.py `
  --docx "C:\path\抗体标签可信度认证表_修订版.docx" `
  --registry configs\label_registry.csv `
  --output configs\label_certification_revision.csv
```

输出接口：

```csv
source_file,document_filename,filename_alias,endpoint_definition,raw_numeric_direction,development_value_direction,certification_label_source,endpoint_grade,affinity_grade,grade_weight,training_head,primary_affinity_weight,comparison_scope,certification_notes,certification_version
```

### 6.2 合并到总标签注册表

```powershell
python scripts/build_label_registry.py `
  --audit data\processed\audit.csv `
  --certification configs\label_certification_revision.csv `
  --output configs\label_registry.csv `
  --overrides configs\direction_overrides.csv
```

### 6.3 生成主亲和力数学路线数据

```powershell
python -m bioos_benchmark.ranking.prepare `
  --input data\processed\curation\curated_sample_with_splits.csv `
  --output artifacts\math_benchmark\dataset.csv `
  --split-column paper_split `
  --label-registry configs\label_registry.csv
```

该接口会自动采用 `primary_affinity_weight`，并在 summary JSON 中列出每个独立任务头被隔离的样本数。

## 7. 验收标准

- Word 表条目数、注册表条目数和匹配数必须都是 83；
- 不允许出现重复 `source_file`；
- AbRank 在拆分前不得进入主亲和力训练；
- OVA 风险、IC50、EC50、ADCC 和二分类不得进入 KD 主头；
- 数学路线的 `registry_rows_missing` 必须为 0；
- 单元测试必须全部通过。

