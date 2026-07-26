# A3：深度模型训练与推理流水线

> 负责人：计算机同学  
> 状态：模块设计完成，代码待实现  
> 前置依赖：A1、A2、公共接口契约

## 模块简介

本模块负责把“表征、模型、损失和数据切分”连接成可复现的训练程序，并提供批量推理接口。它不负责决定数学指标定义，也不修改固定的数据切分。

## Python 接口

计划文件：

```text
src/bioos_benchmark/ai/train_deep.py
src/bioos_benchmark/ai/predict_deep.py
```

```python
def train_deep_ranker(
    config_path: str,
    *,
    fold: int,
    seed: int,
) -> dict[str, object]:
    """训练一个 fold，返回最佳 epoch 和验证指标摘要。"""

def predict_deep_ranker(
    model_dir: str,
    input_path: str,
    output_path: str,
    *,
    split: str | None = None,
) -> None:
    """写出符合公共契约的 predictions.csv。"""
```

## 命令行接口

```bash
bioos-train-deep \
  --config configs/deep_ranker.yaml \
  --fold 0 \
  --seed 42

bioos-predict-deep \
  --model-dir artifacts/deep/fold_0 \
  --input data/processed/canonical_dataset.csv \
  --split validation \
  --output predictions/deep_fold_0.csv
```

## 模型目录规范

```text
artifacts/deep/fold_0/
├── config.resolved.yaml
├── model.pt
├── optimizer.pt
├── metrics.json
├── training_curve.csv
├── data_manifest.json
└── environment.txt
```

至少保存：

- `best`：严格验证指标最好的权重；
- `last`：最后一个 epoch；
- 解析后的完整配置；
- 数据与 split 哈希；
- Python、PyTorch、CUDA、编码器版本。

## 训练顺序

1. 固定随机种子；
2. 读取固定 split；
3. 读取 A1 缓存；
4. 读取 B1 preference pairs；
5. 训练 Deep-v0；
6. 输出验证预测给 B3；
7. Deep-v0 稳定后再训练 Deep-v1；
8. LoRA 只作为后续可选实验。

## 推理输出

输出必须包含：

```csv
record_id,split,source_group,target_id,y_true,score,model_id
```

推理函数不直接生成最终 Rank；统一 Rank 由公共 `scores_to_submission` 完成，避免两条路线使用不同的排序方向。

## 验收标准

- 同一权重、同一输入、同一种子得到相同分数；
- validation/test 不参与梯度更新；
- 能从中断 checkpoint 恢复；
- 输出记录数和输入完全一致；
- `score` 无 NaN/Inf；
- 至少记录 3 个随机种子的结果；
- README 中的一条命令可完成最小训练和推理。
