# A2：三路深度排序器

> 负责人：计算机同学  
> 状态：模块设计完成，代码待实现  
> 前置依赖：A1 表征缓存、公共接口契约

## 模块简介

本模块读取 heavy、light、antigen 三路向量，输出一个连续亲和力分数。分数只要求保持顺序：越大表示预测亲和力越强。

第一版使用轻量 MLP 建立可靠基线；第二版再加入 heavy–light 融合门、抗体–抗原交互和 assay-conditioned 多专家头。所有复杂结构都必须通过严格验证证明有增益。

## 推荐的两级实现

### Deep-v0：最小基线

```text
[heavy, light, antigen, masks]
→ concatenate
→ LayerNorm
→ MLP
→ scalar score
```

### Deep-v1：正式候选

```text
heavy + light + has_light
→ antibody fusion

antibody + antigen + has_antigen
→ gated interaction

interaction + assay embedding
→ mixture-of-experts rank head
→ scalar score
```

## Python 接口

计划文件：`src/bioos_benchmark/ai/deep_ranker.py`

```python
class DeepAffinityRanker:
    def forward(
        self,
        heavy_embedding,
        light_embedding,
        antigen_embedding,
        has_light,
        has_antigen,
        assay_id,
    ):
        """返回 shape=(N,) 的连续分数。"""

    def score_pairs(
        self,
        left_batch: dict,
        right_batch: dict,
    ):
        """返回 score(left) - score(right)，供 pairwise loss 使用。"""

def build_deep_ranker(config: dict) -> DeepAffinityRanker:
    """按配置创建模型，不读取数据。"""
```

## 配置接口

```yaml
model_id: deep_v1
embedding_dim: 1280
hidden_dim: 512
dropout: 0.15
assay_experts:
  - kd
  - ic50_ec50
  - binding
missing_light_gate: true
missing_antigen_gate: true
loss:
  pairwise_weight: 1.0
  listwise_weight: 0.2
```

## 与数学路线的连接点

本模块不自行判断哪些样本可以比较。训练时使用数学路线 B1 输出的 pair：

```text
left_record_id
right_record_id
preference
pair_weight
comparison_group
```

若 B1 尚未完成，可先在相同 `source_group + target_id + assay_family` 内临时构造无并列 pair，但必须标记为临时基线。

## 可调用接口示例

```python
model = build_deep_ranker(config)
left_score_minus_right = model.score_pairs(left_batch, right_batch)
loss = pairwise_loss(
    left_score_minus_right,
    preference=pair_labels,
    weight=pair_weights,
)
```

## 验收标准

- 交换 pair 左右后，分数差符号相反；
- 全部 mask 情况下不产生 NaN；
- VHH 和 Fv 可在同一 batch 中运行；
- 模型不接收 `source_group`、论文 ID、文件 ID；
- Deep-v1 必须在严格验证中稳定优于 Deep-v0，才进入最终集成。
