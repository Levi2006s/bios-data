# B3：严格评价、统计检验与模型集成

> 负责人：数学同学  
> 状态：模块设计完成，代码待实现  
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

计划文件：

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
) -> dict[str, object]:
    """计算全局、宏平均、冷启动和置信区间指标。"""

def percentile_rank_by_group(
    scores: list[float],
    groups: list[str],
) -> list[float]:
    """在指定组内把分数转换为 0～1 百分位。"""

def ensemble_predictions(
    prediction_paths: list[str],
    output_path: str,
    *,
    weights: list[float] | None = None,
) -> None:
    """按 record_id 对齐，百分位化后加权集成。"""
```

## 命令行接口

```bash
bioos-evaluate \
  --truth data/processed/canonical_dataset.csv \
  --predictions predictions/deep_fold_0.csv \
  --output reports/deep_fold_0_metrics.json \
  --bootstrap-rounds 1000

bioos-ensemble \
  --inputs predictions/deep_oof.csv predictions/math_oof.csv \
  --weights 0.6 0.4 \
  --output predictions/ensemble_oof.csv
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

## Go/No-Go 规则

一个新模块进入最终方案必须满足：

- 至少 3 个随机种子中，大多数严格指标改善；
- 95% 置信区间不过度恶化；
- antigen-cold 结果没有明显下降；
- 负对照通过；
- 没有新增泄漏；
- 推理资源在比赛平台预算内。

## 验收标准

- 输入行顺序改变不影响指标；
- 常数预测返回明确的无效/零相关结果，不崩溃；
- 标签打乱结果接近 0；
- 同一预测文件重复计算结果一致；
- 两模型缺少或重复 `record_id` 时直接报错；
- 集成权重、输入哈希和输出哈希写入报告。
