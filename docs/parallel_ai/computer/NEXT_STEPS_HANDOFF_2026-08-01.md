# 计算机学生下一阶段交接计划

> 更新日期：2026-08-03
>
> 负责人：计算机方向同学
>
> 前置状态：数据审计和数学路线第一阶段已经完成
>
> 总目标：在不修改标签和安全划分的前提下，实现可复现的抗体/抗原表征与深度排序模型

## 1. 开始前先理解三件事

1. 当前数学基线在训练偏好对上约有 80% 正确率，但跨来源泛化能力很弱，这是深度模型必须超过的最低基线。
2. 标签方向、标签质量、独立任务头和数据划分已经人工审核，计算机路线不能自行反转标签、混合任务或重新随机划分。
3. 深度模型只负责输出连续 `score`，Spearman、Top-K、置信区间、泄漏审计和最终集成由数学路线统一计算。

数学路线验收结果见：

```text
docs/parallel_ai/math/PHASE1_ACCEPTANCE_REPORT_2026-08-01.md
```

## 2. 可以直接使用的输入

### 标准化样本

```text
data/processed/curation/curated_sample_with_splits.csv
```

正式全量运行时需要从原始数据重新生成，不要把本机 `data/processed` 当作代码提交。

### 标签注册表

```text
configs/label_registry.csv
```

这里记录每个文件的标签含义、方向、单位、质量等级和使用限制。必须读取 `affinity_grade`、`training_head` 和 `primary_affinity_weight`：主亲和力模型只训练 `training_head=affinity_kd`；IC50、EC50、二分类、OVA 风险、ADCC 和未拆分 AbRank 使用独立预测头或暂时排除。

修订规则和接口见：

```text
docs/curation/08_LABEL_CERTIFICATION_REVISION_2026-08-03.md
configs/label_certification_revision.csv
```

### 偏好对

由数学模块生成：

```csv
left_record_id,right_record_id,preference,pair_weight,comparison_group,reason
```

其中 `left_record_id` 是相对更优的抗体，`pair_weight` 是标签可信权重。

### 统一预测输出

任何深度模型必须输出：

```csv
record_id,split,source_group,target_id,y_true,score,model_id
```

`score` 必须是连续数值，而且始终“越大越好”。

## 3. 工作顺序总览

| 优先级 | 工作包 | 预计产物 | 完成标志 |
|---:|---|---|---|
| P0 | 云端环境与接口冒烟测试 | 环境清单、最小日志 | 小样本可从输入走到预测输出 |
| P1 | ANARCII/IMGT编号 | 编号表、CDR掩码 | 2,060条测试链全部给出成功/失败状态 |
| P2 | 冻结序列表征与缓存 | heavy/light/antigen向量 | 重复序列只计算一次，缓存可校验 |
| P3 | Deep-v0最小排序器 | 模型权重、验证预测 | 读数学偏好对并输出统一CSV |
| P4 | 严格训练与推理流水线 | 多种子模型和日志 | 无泄漏，固定种子可复现 |
| P5 | Deep-v1增强实验 | 交互结构与消融报告 | 严格指标稳定优于Deep-v0才保留 |
| P6 | 交付数学路线评估与集成 | OOF/验证预测 | 数学接口可直接读取且ID完全一致 |

按 P0→P6 顺序推进。P0～P4完成以前，不做大规模LoRA或复杂结构模型。

## 4. P0：建立云端可复现环境

### 模块简介

先在云算力平台建立干净环境，并用小样本验证代码、数据和GPU是否可用。目的不是取得高分，而是避免正式运行时才发现版本或接口不兼容。

### 建议资源

- Ubuntu 22.04；
- Python 3.10或3.11；
- 内存至少16 GB；
- 磁盘至少30 GB，若下载多个模型建议100 GB；
- 第一版使用16～24 GB显存GPU即可；
- 大模型或结构模型再申请更高显存。

### 要保存的环境信息

```text
Python版本
PyTorch版本
CUDA与驱动版本
GPU名称和显存
pip freeze
Git commit
运行命令和随机种子
```

### 验收标准

- 能安装当前仓库；
- `pytest -q`通过；
- 能读取标准化CSV和偏好对；
- 能写出10条符合统一预测接口的模拟结果；
- 环境步骤写入Markdown，不只保留在聊天记录中。

## 5. P1：运行ANARCII并提取IMGT/CDR区域

### 模块简介

ANARCII不是亲和力模型。它负责给抗体链进行IMGT编号，并准确找出CDR1、CDR2、CDR3，后续模型才能分别提取CDR和框架区特征。

### 输入

```text
data/processed/curation/imgt_numbering_input.fasta
```

当前测试输入包含2,110条去重后的重链或轻链。

### 输出接口

建议输出：

```csv
sequence_id,chain_type,numbering_status,imgt_numbered_sequence,cdr1,cdr2,cdr3,error
```

### 实现要求

- 记录每条链成功或失败，不允许静默丢失；
- 重链、轻链和VHH要区分；
- 保存ANARCII版本和scheme；
- 先跑2,110条测试链，成功后再跑全量唯一序列；
- 输出通过 `sequence_id` 与原数据关联。

### 验收标准

- 输入条数等于成功数加失败数；
- 同一序列重复运行结果一致；
- 至少人工抽查20条CDR边界；
- 失败原因有汇总统计。

## 6. P2：冻结预训练模型表征并建立缓存

### 模块简介

把氨基酸字符串转成向量。第一版冻结预训练模型，只做前向推理，不更新模型权重。这样资源需求较低，也容易判断“预训练表征本身是否有价值”。

### 模型选择原则

先选择一个较小且许可证允许比赛使用的抗体或蛋白编码器完成闭环。必须记录：

- 模型名称和权重版本；
- 下载地址和许可证；
- 是否专门针对抗体训练；
- 最大序列长度和向量维度；
- 所需显存与推理速度。

不要同时下载和接入很多模型。第一个模型跑通后，再增加第二个模型做公平比较。

### 计划代码接口

```python
class SequenceEncoder:
    def encode(self, sequences: list[str], *, batch_size: int = 32):
        """返回shape=(N,D)的float32向量。"""

def build_embedding_cache(records, encoder, output_dir, *, batch_size=32):
    """去重序列、批量编码并保存可校验缓存。"""
```

详细设计：

```text
docs/parallel_ai/computer/A1_EMBEDDING_BACKEND.md
```

### 缓存输出

```text
artifacts/embeddings/<encoder_id>/
├── manifest.json
├── heavy.npy
├── light.npy
├── antigen.npy
├── masks.npz
└── record_ids.txt
```

### 验收标准

- 相同序列只编码一次；
- VHH的 `has_light=False`；
- 缺失抗原使用mask，不伪造抗原序列；
- 输出为float32且无NaN/Inf；
- `manifest.json`记录数据哈希、模型版本、代码提交和维度；
- 第二次运行能复用缓存。

## 7. P3：实现Deep-v0最小排序器

### 模块简介

Deep-v0只做最简单的向量拼接和MLP打分。它的作用是确认预训练表征能否超过当前字符k-mer数学基线。

### 最小架构

```text
heavy embedding
+ light embedding和has_light
+ antigen embedding和has_antigen
→ LayerNorm
→ 两层MLP
→ 一个连续score
```

### 训练监督

必须直接读取数学路线生成的偏好对：

```text
score(left) - score(right)
→ pairwise logistic loss
→ 乘以pair_weight
```

不能由深度模型自行跨来源构造新的偏好对。

### 计划接口

```python
class DeepAffinityRanker:
    def forward(self, heavy, light, antigen, has_light, has_antigen):
        """输出shape=(N,)的连续分数。"""

    def score_pairs(self, left_batch, right_batch):
        """输出score(left)-score(right)。"""
```

详细设计：

```text
docs/parallel_ai/computer/A2_DEEP_RANKER.md
```

### 验收标准

- 交换pair左右后分数差符号相反；
- 缺失轻链或抗原不会产生NaN；
- 模型输入中没有source_group、source_file、论文ID；
- 可以同时处理Fv与VHH；
- 小样本能够过拟合，用于证明训练链路正确；
- 随后在严格验证集上报告真实结果，不能只报告训练正确率。

## 8. P4：建立严格训练与推理流水线

### 模块简介

将固定划分、embedding缓存、偏好对、模型、检查点和预测输出连接成一条可复现流水线。

### 必须使用的划分

至少分别运行：

1. `paper_split`：检查跨论文来源泛化；
2. `heuristic_family_safe_split`：检查是否依赖相似抗体记忆；
3. 后续具备足够抗原数据时运行 `exact_antigen_safe_split`。

禁止重新随机打散全部行，因为这会重新引入重复抗体泄漏。

### 训练要求

- 至少运行seed 42、43、44；
- validation和test不参与梯度更新；
- 保存best和last检查点；
- 记录训练曲线、学习率、batch size和运行时间；
- 显存不足时优先降低batch size或使用梯度累积；
- 每次训练记录输入数据和split哈希。

### 计划命令接口

```bash
bioos-train-deep --config configs/deep_ranker.yaml --fold 0 --seed 42

bioos-predict-deep \
  --model-dir artifacts/deep/fold_0 \
  --input data/processed/canonical_dataset.csv \
  --split validation \
  --output predictions/deep_fold_0.csv
```

详细设计：

```text
docs/parallel_ai/computer/A3_TRAIN_AND_INFER.md
```

### 验收标准

- 同一权重和输入可复现相同预测；
- 输出ID与输入一一对应；
- `score`无缺失、NaN或Inf；
- 可以从检查点恢复；
- 数学评估模块能直接读取预测文件。

## 9. P5：Deep-v1增强实验

只有Deep-v0完整跑通后才开始。可按顺序尝试：

1. CDR与framework分别pooling；
2. heavy-light门控融合；
3. 抗体-抗原交互层；
4. assay类型的低维条件头；
5. 最后才考虑LoRA微调编码器。

每次只增加一个主要变化，并保存消融结果。若一个模块不能在至少3个随机种子中稳定改善宏平均Spearman和抗体家族隔离结果，就不进入正式方案。

## 10. P6：交付数学路线统一评估

### 需要交付的文件

```text
predictions/deep_paper_seed42.csv
predictions/deep_paper_seed43.csv
predictions/deep_paper_seed44.csv
predictions/deep_family_seed42.csv
artifacts/deep/<run_id>/config.resolved.yaml
artifacts/deep/<run_id>/training_curve.csv
artifacts/deep/<run_id>/environment.txt
```

预测CSV必须符合：

```csv
record_id,split,source_group,target_id,y_true,score,model_id
```

数学同学随后负责：

- Spearman和来源宏平均；
- Top-1%/5%/10%富集率；
- 聚类Bootstrap置信区间；
- 重复抗体和来源记忆检查；
- 与数学基线公平比较；
- OOF百分位集成。

## 11. 第一周建议安排

### 第1天

- 建立云端环境；
- 克隆仓库并通过测试；
- 阅读公共接口和数学验收报告。

### 第2天

- 安装ANARCII；
- 跑2,110条测试链；
- 输出编号成功率和失败清单。

### 第3～4天

- 选择一个冻结编码器；
- 实现序列去重、批量编码和缓存；
- 用100条样本验证向量和mask。

### 第5～6天

- 实现Deep-v0；
- 用小样本过拟合检查方向；
- 使用数学偏好对跑通一个seed。

### 第7天

- 输出第一份验证预测；
- 交给数学评估接口；
- 写模块Markdown和问题清单。

## 12. 每完成一个工作包必须提交什么

每个P0～P6工作包结束时必须提交：

1. 模块简介Markdown；
2. 稳定的Python和命令行接口；
3. 输入、输出和字段说明；
4. 环境与依赖版本；
5. 最小运行示例；
6. 自动测试及真实结果；
7. 已知问题和失败案例；
8. 不进入GitHub的大文件清单及其云端保存位置。

模型权重、embedding缓存和大体积数据不要直接提交普通Git仓库。GitHub中保存代码、配置、轻量示例、结果摘要和复现文档。

## 13. 最终验收线

计算机路线第一轮完成需要同时满足：

- ANARCII编号流程可复现；
- 冻结embedding缓存可复用；
- Deep-v0能读取数学偏好对并输出统一预测；
- 三个随机种子均有结果；
- 论文来源隔离和抗体家族隔离均已评估；
- 不使用来源元数据作为特征；
- 没有跨split重复抗体；
- 指标至少与数学k-mer基线公平比较；
- README中的最小命令能在干净云实例运行。

第一轮目标不是立刻达到SOTA，而是得到一个没有泄漏、接口稳定、可复现、可以继续增强的深度学习基线。
