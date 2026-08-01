# B3：严格评价、统计检验与模型集成

> 负责人：数学同学  
> 状态：已实现并验证  
> 评价实现：`src/bioos_benchmark/ranking/evaluation.py`  
> 集成与提交实现：`src/bioos_benchmark/ranking/ensemble.py`  
> 测试位置：`tests/test_math_evaluation.py`  
> 输入：任意符合公共契约的预测文件

## 模块简介

本模块是两条路线共同使用的“裁判”。它只读取真实标签、固定 split 和模型预测，不依赖模型内部实现。

核心任务：

1. 计算严格切分的多维 Spearman；
2. 用 bootstrap 给出置信区间；
3. 执行标签打乱和 metadata-only 负对照；
4. 比较两条路线；
5. 用 OOF percentile rank 做集成。

## Python 接口

实现文件：

```text
src/bioos_benchmark/ranking/evaluation.py
src/bioos_benchmark/ranking/ensemble.py
```

```python
def evaluate_predictions(
    truth_path: str,
    prediction_path: str,
    *,
    bootstrap_rounds: int = 1000,
    seed: int = 42,
    split: str | None = None,
) -> dict[str, object]:
    """计算全局、宏平均、冷启动和置信区间指标。"""

def percentile_rank_by_group(
    scores: list[float],
    groups: list[str],
) -> list[float]:
    """在指定组内把分数转换为 0～1 百分位。"""

def ensemble_predictions(
    prediction_paths: list[str | Path],
    output_path: str | Path,
    *,
    weights: list[float] | None = None,
    group_field: str = "target_id",
) -> dict[str, object]:
    """按 record_id 对齐，百分位化后加权集成。"""

def scores_to_submission(
    records_path: str | Path,
    predictions_path: str | Path,
    output_path: str | Path,
    *,
    split: str | None = None,
) -> dict[str, object]:
    """生成官方 VH/VHH、VL、Rank 文件。"""
```

## 命令行接口

```bash
bioos-evaluate \
  --truth data/processed/canonical_dataset.csv \
  --predictions predictions/deep_fold_0.csv \
  --split validation \
  --output reports/deep_fold_0_metrics.json \
  --bootstrap-rounds 1000

bioos-ensemble \
  --inputs predictions/deep_oof.csv predictions/math_oof.csv \
  --weights 0.6 0.4 \
  --group-field target_id \
  --output predictions/ensemble_oof.csv

bioos-submit \
  --input data/processed/test.csv \
  --predictions predictions/ensemble_test.csv \
  --split test \
  --output submission.csv
```

## 必报指标

- global Spearman；
- macro source/target Spearman；
- size-weighted Spearman；
- source-held-out Spearman；
- antigen-cold Spearman；
- Fv 与 VHH 分层 Spearman；
- 截断与非截断样本分层结果；
- bootstrap 95% 置信区间；
- pair accuracy；
- Top-10% enrichment。

内部模型选择分数：

```text
0.50 × macro landscape Spearman
+ 0.25 × source-held-out Spearman
+ 0.25 × antigen-cold Spearman
```

如果官方规则更新，只修改配置，不修改历史报告。

只有输入中明确包含：

```text
evaluation_regime = source-held-out
evaluation_regime = antigen-cold
```

时，程序才计算对应指标和内部综合分数。字段不存在时结果写为 `null`，避免把普通验证集错误宣称为冷启动验证。

## 集成规则

不能直接平均不同模型的原始分数。推荐：

```text
每个 fold 的 score
→ fold/目标内 percentile rank
→ 按 record_id 对齐
→ OOF 确定权重
→ 加权平均
→ 最终 Rank
```

权重只能用 OOF/validation 结果选择，不能查看测试标签。

集成会额外生成：

```text
ensemble.csv
ensemble.summary.json
```

summary 记录每个输入文件的 SHA-256、归一化权重、模型 ID、分组字段和输出 SHA-256。

## 当前评价报告

当前实现输出：

- global Spearman、Pearson、RMSE、MAE、Top-10% enrichment；
- macro/size-weighted source Spearman；
- macro/size-weighted target Spearman；
- 按 split、抗体类型、截断状态分层指标；
- 基于 `split_group` 或 `source_group` 的 cluster bootstrap 95% 区间；
- 固定随机种子的标签打乱 Spearman；
- 有显式验证场景时的模型选择综合分数。

注意：按靶点百分位化后，不同靶点的绝对值不再强行可比。因此集成优先关注 macro target/source Spearman；全局 Spearman 仍报告，但不能单独决定模型。

## Go/No-Go 规则

一个新模块进入最终方案必须满足：

- 至少 3 个随机种子中，大多数严格指标改善；
- 95% 置信区间不过度恶化；
- antigen-cold 结果没有明显下降；
- 负对照通过；
- 没有新增泄漏；
- 推理资源在比赛平台预算内。

## 验收结果

- 输入行顺序改变不影响指标；
- 常数预测返回明确的无效/零相关结果，不崩溃；
- 标签打乱结果接近 0；
- 同一预测文件重复计算结果一致；
- 两模型缺少或重复 `record_id` 时直接报错；
- 集成权重、输入哈希和输出哈希写入报告。

实际测试：

```bash
$env:PYTHONPATH="src"
python -m pytest -q \
  tests/test_math_preferences.py \
  tests/test_math_ranker.py \
  tests/test_math_evaluation.py
```

```text
14 passed in 1.41s
```

已验证：

- 完美预测得到 Spearman 1；
- 输入行顺序改变不影响结果；
- 缺少 `record_id` 会直接报错；
- 并列分数得到平均百分位；
- 两模型可按权重完成集成并写 summary；
- 按目标百分位集成保持组内正确排序；
- 最终 Rank 从 1 连续编号；
- VHH 的 VL 保持空；
- 没有显式冷启动场景时综合分数为 `null`。

## 变更记录

| 日期 | 版本 | 修改 |
|---|---|---|
| 2026-07-26 | v0.1 | 实现严格评价、cluster bootstrap、百分位集成、提交生成和测试 |
