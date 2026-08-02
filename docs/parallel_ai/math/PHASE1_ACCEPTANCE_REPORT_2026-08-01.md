# 数学路线第一阶段验收报告

> 日期：2026-08-01
>
> 状态：五个模块已实现、已在标准化审计样本上运行
>
> 边界：这是 3,964 条分层样本上的工程基准，不是 2,009,775 条全量数据的最终比赛成绩

> 2026-08-03 修订：已按新版抗体标签可信度认证表重跑主 KD 路线。下列主结果使用修订后的任务隔离和等级权重；旧的跨任务混合结果不再作为当前基线。

## 1. 总结结论

本阶段已经完成：

1. 把连续标签转换成“抗体 A 优于抗体 B”的偏好对；
2. 建立可解释的成对逻辑回归排序基线；
3. 计算 Spearman、Top-1%/5%/10% 富集率及聚类 Bootstrap 置信区间；
4. 检查完整抗体、重链、来源组和来源文件是否跨集合重复；
5. 验证多个预测文件按 ID 对齐、百分位化和加权集成的接口。

最重要的结果不是“分数很高”，而是：简单模型在训练偏好上约有 80% 正确率，但跨新论文或新抗体家族时表现较弱。因此当前模型适合作为后续复杂模型必须超过的基线，不适合直接作为最终方案。

## 2. 本次使用的数据

输入文件：

```text
data/processed/curation/curated_sample_with_splits.csv
```

输入共 3,964 条，来自已经人工审核的 83 个 CSV。新版认证把非 KD 终点隔离后，主亲和力路线保留 2,565 条：训练 1,945、验证 120、测试 500；另有 1,399 条留给独立任务头。

标签质量权重改为：

| 等级 | 权重 |
|---|---:|
| A | 1.000 |
| A/B | 0.875 |
| B | 0.750 |
| B/C | 0.625 |
| C | 0.500 |
| C/D | 0.250 |
| D、NA | 0.000 |

主评估采用论文来源隔离。IC50、EC50、相对结合、二分类、OVA 风险、ADCC 和未拆分 AbRank 不进入当前 KD 排序头。

## 3. 模块一：偏好对

### 模块简介

只在同一个数据文件、抗原和检测类型内比较两个抗体。如果统一方向后的标签 A 大于 B，则建立“A 优于 B”。并列样本不生成强偏好，低质量标签会降低 pair 权重。

论文隔离训练集生成 45,195 个有效偏好对，涉及 58 个可比较实验组。所有 pair 均通过方向、跨 split、跨实验组和重复检查。

### 接口

```bash
python -m bioos_benchmark.ranking.prepare \
  --input data/processed/curation/curated_sample_with_splits.csv \
  --output artifacts/math_benchmark/dataset.csv \
  --split-column paper_split \
  --label-registry configs/label_registry.csv

python -m bioos_benchmark.ranking.preferences \
  --input artifacts/math_benchmark/dataset.csv \
  --output artifacts/math_benchmark/pairs_train.csv \
  --split train --seed 42
```

偏好对接口：

```csv
left_record_id,right_record_id,preference,pair_weight,comparison_group,reason
```

`left_record_id` 表示较优抗体，当前标准方向下 `preference=1`。

## 4. 模块二：可解释数学排序基线

### 模块简介

模型使用抗体重链、轻链和可用抗原序列的 2～4 字符 k-mer，以及长度、疏水比例、净电荷、半胱氨酸和脯氨酸比例。训练目标是让较优抗体分数高于较差抗体。

模型不读取 `source_group`、`source_file`、论文名或 `record_id` 作为特征。

### 接口

```bash
python -m bioos_benchmark.ranking.math_ranker train \
  --input artifacts/math_benchmark/dataset.csv \
  --pairs artifacts/math_benchmark/pairs_train.csv \
  --artifact-dir artifacts/math_benchmark/model_seed42 \
  --seed 42
```

主要 Python 接口：

```python
FeaturePairwiseRanker.fit(records, pairs)
FeaturePairwiseRanker.predict_score(records)
FeaturePairwiseRanker.save(output_dir)
```

论文隔离训练集中：

| 随机种子 | 偏好对数量 | 训练 pair accuracy |
|---:|---:|---:|
| 42 | 45,195 | 0.8035 |
| 43 | 45,195 | 0.8046 |

## 5. 模块三：Spearman、Top-K和置信区间

### 模块简介

Spearman 衡量整体次序；Top-K 富集率大于 1 表示预测前 K% 比随机选择更容易找到真正的前 K%；聚类 Bootstrap 以来源组为单位重复抽样，避免把同一实验内样本错误当成完全独立。

### 论文来源隔离验证集结果

| 模型 | 全局 Spearman | 宏平均 Spearman | Top-5% | Top-10% | Spearman 95% CI | Top-10% 95% CI |
|---|---:|---:|---:|---:|---|---|
| seed 42 | -0.0655 | 0.3288 | 0.0000 | 1.6667 | [-0.1153, 0.7729] | [0.0, 1.6667] |
| seed 43 | -0.0659 | 0.3287 | 0.0000 | 1.6667 | [-0.1159, 0.7729] | [0.0, 1.6667] |
| 50/50 集成 | 0.0466 | 0.3288 | 0.0000 | 0.0000 | [-0.1153, 0.7729] | [0.0, 0.0] |

验证集只有 2 个独立来源组、共 120 条，其中一个来源只有 20 条且 Spearman 较高，使宏平均和置信区间非常不稳定。不能据此声称模型已经有效泛化。

### 相似抗体家族隔离测试结果（修订前历史结果）

| 样本数 | 全局 Spearman | 来源宏平均 Spearman | Top-5% | Top-10% | Spearman 95% CI | Top-10% 95% CI |
|---:|---:|---:|---:|---:|---|---|
| 500 | 0.1307 | 0.0181 | 0.8 | 1.6 | [-0.1197, 0.1559] | [0.0, 1.6] |

该表使用旧标签混合策略，仅保留作历史对照，不与修订后主结果直接比较。下一轮全量云端实验需按新版认证重新运行家族隔离测试。

### 接口

```bash
python -m bioos_benchmark.ranking.evaluation \
  --truth artifacts/math_benchmark/dataset.csv \
  --predictions artifacts/math_benchmark/predictions_validation_seed42.csv \
  --split validation \
  --bootstrap-rounds 1000 \
  --output artifacts/math_benchmark/evaluation_validation_seed42.json
```

## 6. 模块四：重复和来源记忆检查

### 模块简介

该模块检查评估样本的完整重链+轻链、单独重链、来源组和来源文件是否在训练集中出现，并建立“查表记忆”对照。如果没有见过对应键，对照只能返回训练集全局均值，其 Spearman 应当无定义或接近 0。

### 实际结果

| 划分 | 评估样本 | 完整抗体重合 | 重链重合 | 来源组重合 | 来源文件重合 |
|---|---:|---:|---:|---:|---:|
| 论文来源隔离验证 | 120 | 0 | 0 | 0 | 0 |
| 抗体家族隔离测试 | 500 | 0 | 0 | 0 | 0 |

因此，本次分数不能由“直接记住完全相同抗体”或“直接读取来源编号”解释。但这不等于完全排除相似序列记忆：当前家族桶是确定性启发式分组，正式全量实验还应在云端使用 MMseqs2/CD-HIT 或等价方法做序列同一性聚类。

### 接口

```bash
python -m bioos_benchmark.ranking.leakage \
  --truth artifacts/math_benchmark/dataset.csv \
  --predictions artifacts/math_benchmark/ensemble_validation.csv \
  --evaluation-split validation \
  --output artifacts/math_benchmark/shortcut_audit_validation.json
```

## 7. 模块五：多个模型预测集成

### 模块简介

不同模型的原始分数尺度不同，不能直接相加。程序先按目标把每个模型分数转换成 0～1 百分位，再按 `record_id` 对齐并加权平均。

### 接口

```bash
python -m bioos_benchmark.ranking.ensemble ensemble \
  --inputs predictions/model_a.csv predictions/model_b.csv \
  --weights 0.5 0.5 \
  --group-field target_id \
  --output predictions/ensemble.csv
```

本次用两个不同随机种子的同类模型验证了接口。集成没有稳定改善 Top-10% 或置信区间，所以它只证明“组合流程能用”，不证明“当前组合值得进入最终方案”。以后应组合误差互补的数学模型和深度模型，并且只能用验证集或 OOF 结果选择权重。

## 8. 一键复现接口

Windows：

```powershell
.\scripts\run_math_benchmark.ps1 `
  -InputPath data\processed\curation\curated_sample_with_splits.csv `
  -SplitColumn paper_split `
  -EvaluationSplit validation `
  -WorkDir artifacts\math_benchmark
```

该 Windows 脚本已使用仓库内 12 条演示数据实际跑通：数据准备、偏好对、两个随机种子、评价、集成和记忆审计均能连续完成。

Linux：

```bash
bash scripts/run_math_benchmark.sh \
  data/processed/curation/curated_sample_with_splits.csv \
  artifacts/math_benchmark \
  paper_split validation
```

## 9. 当前判断与下一步

五个工程模块已经完成，可交给计算机同学调用。但数学路线还需要继续：

1. 在 2,009,775 条全量可监督数据上运行相同流程；
2. 用真正的序列同一性聚类替代启发式家族桶；
3. 增加按来源平衡的训练抽样，避免大来源控制模型；
4. 在计算机路线输出 IgLM/蛋白语言模型表示后，保持相同划分重新训练；
5. 只有严格验证结果稳定超过当前基线，才能进入最终集成。

当前结论：接口和审计方法合格，简单排序基线的泛化能力不合格，不能作为最终比赛模型。
