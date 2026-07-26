# A1：冻结表征与缓存模块

> 负责人：计算机同学  
> 状态：模块设计完成，代码待实现  
> 目标：把 heavy/VHH、light、antigen 序列转换为可复用的固定长度向量

## 模块简介

本模块相当于“序列翻译器”：把氨基酸字符串转换成模型能处理的数字向量。第一版冻结预训练模型，只做推理和缓存，不从头训练，也暂不使用 LoRA。

建议先选择资源消耗较小、授权允许比赛使用的蛋白或抗体编码器完成闭环，再比较更大模型。heavy、light、antigen 必须分别编码，不能简单拼成一条假序列。

## 输入与输出

输入：

- `RankingRecord` 列表；
- 编码器名称和版本；
- pooling 方法；
- batch size 和设备。

输出目录：

```text
artifacts/embeddings/<encoder_id>/
├── manifest.json
├── heavy.npy
├── light.npy
├── antigen.npy
├── masks.npz
└── record_ids.txt
```

`manifest.json` 必须记录模型名、权重版本、维度、数据哈希、代码提交和生成时间。

## Python 接口

计划文件：`src/bioos_benchmark/ai/embeddings.py`

```python
class SequenceEncoder:
    def encode(
        self,
        sequences: list[str],
        *,
        batch_size: int = 32,
    ) -> "numpy.ndarray":
        """返回 shape=(N, D) 的 float32 向量。"""

def build_embedding_cache(
    records: list["RankingRecord"],
    encoder: SequenceEncoder,
    output_dir: str,
    *,
    batch_size: int = 32,
) -> dict[str, object]:
    """去重序列、批量编码并写入可校验缓存。"""

def load_embedding_batch(
    cache_dir: str,
    record_ids: list[str],
) -> dict[str, "numpy.ndarray"]:
    """按 record_id 返回 heavy/light/antigen 向量和缺失掩码。"""
```

返回键：

```text
heavy
light
antigen
has_light
has_antigen
```

## 命令行接口

```bash
bioos-embed \
  --input data/processed/canonical_dataset.csv \
  --encoder <encoder-name> \
  --output-dir artifacts/embeddings/<encoder-id> \
  --batch-size 32 \
  --device cuda
```

## 实现要求

- 相同序列只编码一次；
- 空 light/antigen 使用零向量加显式 mask，不能伪造序列；
- 缓存的 `record_ids` 与数据一一对应；
- 输出统一为 float32；
- 支持 CUDA 显存不足时自动降低 batch size；
- 训练、验证、测试可共用冻结编码器，但缓存中不能写入标签。

## 最小测试

```python
batch = load_embedding_batch(cache_dir, ["rec_001", "rec_002"])
assert batch["heavy"].shape[0] == 2
assert batch["heavy"].dtype.name == "float32"
assert batch["has_light"].shape == (2,)
```

完成验收：

- 小样本端到端生成缓存；
- 重复序列的向量完全一致；
- VHH 的 `has_light=False`；
- CPU 和 GPU 输出误差在容许范围内；
- 重新运行时能复用已有缓存。
