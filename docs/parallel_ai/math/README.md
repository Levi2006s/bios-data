# 数学学生路线：一步一步运行

> 状态：B1、B2、B3 已完成基础实现并通过自动测试  
> 适用输入：当前数据处理流程生成的 `benchmark_with_split.csv`  
> 分数方向：所有模块统一为“越大越好”

## 1. 这条路线做什么

数学路线把原始的“预测一个绝对亲和力数值”改写为更符合比赛指标的问题：

```text
在相同实验条件下，抗体 A 是否应该排在抗体 B 前面？
```

完整过程：

```text
规范化数据
→ B1 构造可信 preference pair
→ B2 训练质量加权 pairwise 排序器
→ B3 严格评价
→ 多模型百分位集成（有多个模型时）
→ 连续 Rank 提交文件
```

## 2. 安装

在仓库根目录执行：

```bash
python -m venv .venv
```

Windows：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Linux：

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

如果当前机器缺少构建工具，暂时无法执行可编辑安装，但依赖已经存在，可以在仓库根目录直接设置源码路径：

Windows：

```powershell
$env:PYTHONPATH="src"
```

Linux：

```bash
export PYTHONPATH=src
```

后续 `python -m ...` 命令仍可正常运行。一键脚本会自动完成这项设置。

## 3. 准备输入

数学路线使用数据处理模块的拆分结果：

```text
data/processed/benchmark_with_split.csv
```

最少需要：

```text
record_id
heavy
light
antigen_seq
source_file
source_group
antigen_id
score
split
```

其中：

- `score` 越大越好；
- `split` 为 `train / validation / test`；
- 相同实验来源使用相同 `source_file + antigen_id`。

当前新版注册表已经提供 `label_quality` 的来源权重、`affinity_grade`、`training_head` 和 `certification_version`。`bioos-prepare-math` 会自动保留 `primary_affinity_weight>0` 的主 KD 数据，并隔离 IC50、EC50、二分类、OVA 风险、ADCC 和未拆分 AbRank。未来加入 `canonical_label`、`is_censored` 等逐记录字段后，代码仍会优先使用更严格的字段。

## 4. 第一步：生成偏好 pair

```bash
python -m bioos_benchmark.ranking.preferences \
  --input data/processed/benchmark_with_split.csv \
  --output artifacts/math/pairs_train.csv \
  --split train \
  --max-pairs-per-group 100000 \
  --max-pairs-total 1000000 \
  --seed 42
```

输出：

```text
artifacts/math/pairs_train.csv
artifacts/math/pairs_train.summary.json
```

对应模块说明：[B1_PREFERENCE_GRAPH.md](B1_PREFERENCE_GRAPH.md)

## 5. 第二步：训练数学排序模型

```bash
python -m bioos_benchmark.ranking.math_ranker train \
  --input data/processed/benchmark_with_split.csv \
  --pairs artifacts/math/pairs_train.csv \
  --artifact-dir artifacts/math/model \
  --seed 42
```

输出：

```text
artifacts/math/model/model.joblib
artifacts/math/model/config.json
artifacts/math/model/metrics.json
artifacts/math/model/predictions_validation.csv
```

当前模型使用：

- heavy、light、antigen 的字符 k-mer；
- 长度、疏水性、净电荷、半胱氨酸、脯氨酸比例；
- pairwise logistic loss；
- B1 给出的 pair 质量权重。

对应模块说明：[B2_MATHEMATICAL_RANKER.md](B2_MATHEMATICAL_RANKER.md)

## 6. 第三步：验证集推理与评价

```bash
python -m bioos_benchmark.ranking.math_ranker predict \
  --model-dir artifacts/math/model \
  --input data/processed/benchmark_with_split.csv \
  --split validation \
  --output artifacts/math/predictions_validation.csv

python -m bioos_benchmark.ranking.evaluation \
  --truth data/processed/benchmark_with_split.csv \
  --predictions artifacts/math/predictions_validation.csv \
  --split validation \
  --output artifacts/math/evaluation_validation.json \
  --bootstrap-rounds 1000 \
  --seed 42
```

先看：

```text
global.spearman
macro_source_spearman
macro_target_spearman
bootstrap_spearman_95ci
label_permutation_spearman
```

对应模块说明：[B3_EVALUATION_AND_ENSEMBLE.md](B3_EVALUATION_AND_ENSEMBLE.md)

## 7. 第四步：测试集预测与提交

```bash
python -m bioos_benchmark.ranking.math_ranker predict \
  --model-dir artifacts/math/model \
  --input data/processed/benchmark_with_split.csv \
  --split test \
  --output artifacts/math/predictions_test.csv

python -m bioos_benchmark.ranking.ensemble submit \
  --input data/processed/benchmark_with_split.csv \
  --predictions artifacts/math/predictions_test.csv \
  --split test \
  --output artifacts/math/submission.csv
```

`submission.csv` 的字段为：

```csv
VH/VHH,VL,Rank
```

## 8. 有两个以上模型时做集成

例如训练 `seed=42` 和 `seed=43` 两个模型，先分别生成同一批样本的预测，再执行：

```bash
python -m bioos_benchmark.ranking.ensemble ensemble \
  --inputs \
    artifacts/math_seed42/predictions_test.csv \
    artifacts/math_seed43/predictions_test.csv \
  --weights 0.5 0.5 \
  --group-field target_id \
  --output artifacts/math/ensemble_test.csv
```

权重必须使用 validation/OOF 结果确定，不能查看测试标签。

## 9. 一键运行

一键脚本会直接设置 `PYTHONPATH`，因此只要依赖已经安装，就不要求先执行可编辑安装。

Windows：

```powershell
.\scripts\run_math_pipeline.ps1 `
  -Input data\processed\benchmark_with_split.csv `
  -WorkDir artifacts\math `
  -Seed 42
```

Linux：

```bash
bash scripts/run_math_pipeline.sh \
  data/processed/benchmark_with_split.csv \
  artifacts/math \
  42
```

## 10. 已验证的演示案例

仓库提供：

```text
examples/math_demo.csv
```

Windows 实际运行命令：

```powershell
.\scripts\run_math_pipeline.ps1 `
  -Input examples\math_demo.csv `
  -WorkDir artifacts\math_demo `
  -Seed 42 `
  -MaxPairsPerGroup 1000
```

2026-07-26 实际结果：

```text
训练样本：6
偏好 pair：15
训练 pair accuracy：1.0
验证样本：3
验证 Spearman：1.0
测试样本：3
最终 Rank：1～3 连续
```

这只是检查接口和方向是否正确的小型合成演示，不能代表比赛真实性能。

## 11. 测试

只测试数学路线：

```bash
pytest -q \
  tests/test_math_preferences.py \
  tests/test_math_ranker.py \
  tests/test_math_evaluation.py
```

完整项目：

```bash
pytest -q
```

实际结果：

```text
数学路线：14 passed in 1.41s
完整项目：19 passed in 1.48s
```

## 12. 当前能力边界

已完成：

- 方向统一后的 preference pair；
- 并列、截断、冲突和质量权重处理；
- Bradley–Terry 偏好图诊断；
- 可泛化到新序列的 pairwise 模型；
- 严格 ID 对齐评价；
- cluster bootstrap；
- 百分位集成；
- 官方 Rank 文件生成。

尚未完成：

- 83 个文件的人工 label registry；
- connected-component 级全量去重；
- 显式 source-held-out 和 antigen-cold split；
- PLM embedding 接入；
- LambdaRank/GBDT 可选后端；
- 全量数据上的真实性能报告。

这些属于数据完备和模型增强阶段，不影响当前代码闭环运行，但在正式比赛前必须逐项补齐。
