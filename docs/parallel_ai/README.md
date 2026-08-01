# AI 模块双路线并行开发方案

> 依据：`idea.md` 中的初赛方案与当前仓库的数据处理基线  
> 适用阶段：初赛——抗原–抗体亲和力排序  
> 文档状态：方案已完成；数学路线 B1/B2/B3 已实现并验证，计算机路线待实现

## 1. 为什么拆成两条路线

初赛只关心候选抗体的相对次序，主指标是 Spearman 相关系数。为了让两位同学同时推进，并降低单一路线失败的风险，项目采用两条可以独立训练、独立推理的模型路线：

| 路线 | 负责人 | 核心思路 | 独立产物 |
|---|---|---|---|
| A：深度表征排序 | 计算机同学 | 冻结蛋白语言模型，编码 heavy、light、antigen，再训练三路排序网络 | `predictions/deep_ranker.csv` |
| B：数学偏好排序 | 数学同学 | 构造可信的样本偏好关系，用质量加权的排序模型学习相对大小 | `predictions/math_ranker.csv` |

两条路线都读取同一份规范化数据，都输出 `record_id + score`。因此任何一条先完成，都能直接参加评价；两条都完成后再做百分位集成。

## 2. 总体数据流

```text
规范化数据 + 固定 split manifest
             │
       ┌─────┴─────┐
       │           │
路线 A：深度模型   路线 B：数学模型
PLM embedding      偏好 pair / 质量权重
三路交互排序       Bradley–Terry / LambdaRank
       │           │
       └─────┬─────┘
             │
统一 predictions.csv
             │
严格 Spearman 评价 + percentile-rank 集成
             │
       最终 VH/VHH、VL、Rank
```

## 3. 共同约定

两位同学开始编码前，先共同确认 [公共数据与接口契约](SHARED_INTERFACES.md)。接口一旦冻结，若确需修改，必须同时更新：

1. `SHARED_INTERFACES.md`；
2. 受影响模块的 Markdown；
3. 对应自动测试。

禁止把文件名、论文编号、PDB ID 等来源标识直接作为模型特征。它们只能用于分组、切分和评价，防止模型记住数据来源。

## 4. 路线 A：计算机同学

### A1. 冻结表征与缓存

文档：[A1_EMBEDDING_BACKEND.md](computer/A1_EMBEDDING_BACKEND.md)

把 heavy/VHH、light 和 antigen 编码为固定长度向量。先冻结编码器并缓存唯一序列，暂不做 LoRA。

### A2. 三路深度排序器

文档：[A2_DEEP_RANKER.md](computer/A2_DEEP_RANKER.md)

实现 heavy–light 融合、antibody–antigen 交互、缺失轻链/抗原门控和 assay-conditioned 排序头。

### A3. 训练与推理流水线

文档：[A3_TRAIN_AND_INFER.md](computer/A3_TRAIN_AND_INFER.md)

完成训练、断点保存、批量打分、生成连续 Rank，以及统一的预测文件。

## 5. 路线 B：数学同学

### B1. 偏好关系与质量权重

文档：[B1_PREFERENCE_GRAPH.md](math/B1_PREFERENCE_GRAPH.md)

只在可比较的实验上下文内构造“样本 i 优于样本 j”，正确处理方向、并列、截断和重复冲突。

### B2. 可解释排序模型

文档：[B2_MATHEMATICAL_RANKER.md](math/B2_MATHEMATICAL_RANKER.md)

实现 Bradley–Terry 基线和质量加权 LambdaRank/成对排序模型，输出连续分数。

### B3. 严格评价与集成

文档：[B3_EVALUATION_AND_ENSEMBLE.md](math/B3_EVALUATION_AND_ENSEMBLE.md)

计算严格切分下的 Spearman、置信区间、负对照和两路线百分位集成。

数学路线的完整运行顺序见：[math/README.md](math/README.md)。

## 6. 三个并行里程碑

### 里程碑 1：各自跑通最小闭环

计算机同学：

- 用一个小型预训练编码器生成 embedding；
- 用简单 MLP 输出分数；
- 生成符合公共接口的预测文件。

数学同学：

- 生成可信 preference pair；
- 跑通 Bradley–Terry 或简单 pairwise logistic；
- 生成同格式预测文件。

验收：两条路线均能在固定验证集上输出 Spearman。

### 里程碑 2：分别提升

计算机同学加入三路交互、CDR/global pooling、多专家头和门控。

数学同学加入标签质量权重、截断感知、source-balanced 采样、严格置信区间与 LambdaRank。

验收：新模块在至少 3 个随机种子中，大多数结果优于各自最小基线。

### 里程碑 3：联合

- 检查两条路线的错误是否互补；
- 把各模型分数先转为 fold 内 percentile rank；
- 用 OOF 结果确定集成权重；
- 输出最终连续 Rank。

验收：集成结果必须在严格验证集上优于或不劣于最好的单模型，并通过泄漏检查。

## 7. Git 协作边界

建议分支：

```text
feature/computer-deep-ranker
feature/math-ranking
```

建议代码目录：

```text
src/bioos_benchmark/ai/          # 计算机同学维护
src/bioos_benchmark/ranking/     # 数学同学维护
src/bioos_benchmark/contracts.py # 共同维护，谨慎修改
```

两位同学不要同时修改同一个训练入口。各自先保留独立入口：

```text
bioos-train-deep
bioos-train-math
```

最终集成入口由数学路线提供：

```text
bioos-ensemble
```

## 8. 每完成一个模块必须留下什么

每个模块完成时必须：

1. 用 [模块文档模板](MODULE_DOC_TEMPLATE.md) 更新该模块 Markdown；
2. 把状态改为“已实现并验证”；
3. 列出稳定的 Python API 和命令行 API；
4. 写明输入、输出、异常和依赖；
5. 提供最小调用示例；
6. 写明测试命令和实际结果；
7. 记录模型权重、配置和数据版本。

“代码能在作者电脑运行”不算完成；文档中的示例在干净环境可运行，才算完成。
