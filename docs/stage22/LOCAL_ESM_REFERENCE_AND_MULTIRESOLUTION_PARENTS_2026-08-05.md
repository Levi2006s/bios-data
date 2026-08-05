# 阶段 22：局部 ESM 参考与多分辨率父本

## 阶段结论

本阶段验证两项升级：同簇 ESM 最近训练参考的残基差分，以及 8/16 簇多分辨率父本模型。16 簇外层单模达到 Spearman **0.447547**，但按内层选定权重进行一次性外层确认后，Stage 22 融合为 **0.462285**，略低于 Stage 21 的 **0.462519**。因此 Stage 22 不替换正式模型；当前推荐仍为 Stage 21。

这是一次有结论的拒绝实验：它确认细粒度父簇有信息，同时证明 mean-pooled ESM 最近邻不能可靠替代真实实验母本。

## 研究问题

Stage 21 每个 train-only 父簇只用一个逐位置多数共识。它可能把多个亚家族平均成并不存在的序列。本阶段问：

1. 每条样本使用同簇 ESM 最近的训练抗体作为局部参考，是否比硬共识更好？
2. 将每个 assay/长度组从 8 簇提高到 16 簇，能否捕捉更细父本结构？
3. 两者能否在不查看外层标签调权的条件下稳定提升 Stage 21？

## 无泄漏局部参考

连接标准化重链和轻链 ESM150 均值向量，余弦最近参考定义为：

\[
r^*(x)=\arg\max_{r\in T_{c(x)}}\cos(e_{HL}(x),e_{HL}(r)).
\]

- 训练样本：候选只来自同一训练簇，并排除自身；
- 验证样本：候选只来自对应训练簇；
- 聚类、候选库和参考序列均不读取验证标签。

外层共处理 131,164 个唯一重轻链对。最近邻相似度中位数普遍接近 0.999，这说明全局均值 ESM 对近缘突变体非常平滑，也提示“数值最近”未必能定位实验父本。

## 内层结构与权重选择

所有选择仅使用 `stage21_inner_family_split`：

| 内层模型/融合 | Spearman |
|---|---:|
| Stage 21 父本子集成 | 0.646403 |
| 局部参考差分单模 | 0.617847 |
| 90% Stage 21 父本 + 10% 局部差分 | 0.646675 |
| 16 簇绝对父本单模 | 0.637243 |
| 再加入 27.5% 的 16 簇模型 | **0.648478** |

16 簇权重在 25%–30% 附近形成平缓平台，最终固定 27.5%。外层不进行任何权重搜索。

## 外层预注册公式

令 \(R\) 为平均百分位秩，Stage 21 父本子集成为：

\[
P_{21}=0.675R(P_{K8})+0.325R(P_{consensus\text{-}\Delta}).
\]

Stage 22 父本子集成为：

\[
P_{22}=0.725[0.9P_{21}+0.1R(P_{local\text{-}\Delta})]+0.275R(P_{K16}).
\]

最终：

\[
S_{22}=0.775R(S_{17})+0.225P_{22}.
\]

等效权重为 Stage17 77.5%、K8 绝对父本 9.9098%、共识差分 4.7714%、局部差分 1.6313%、K16 绝对父本 6.1875%。

## 外层结果

严格 `global_family_v2_split`，生物学唯一去重验证 \(n=94,848\)：

| 模型 | Spearman |
|---|---:|
| Stage17 | 0.461437 |
| K8 绝对父本 | 0.452528 |
| 共识父本差分 | 0.443089 |
| 局部父本差分 | 0.434411 |
| K16 绝对父本 | **0.447547** |
| Stage21 正式融合 | **0.462519** |
| Stage22 预注册融合 | 0.462285 |

Stage 22 其他指标：Pearson 0.479945，Top-10 enrichment 4.2340；landscape1 Spearman 0.275847，landscape2 0.656338。

相对 Stage 21：

\[
\Delta\rho=0.462285-0.462519=-0.000234.
\]

幅度很小，但晋升规则只看预注册外层是否超过当前最佳，因此明确拒绝晋升，不再以外层结果反向调权。

## 为什么内层提升没有复现

1. 内层增益只有约 0.0021，容易受 family 构成变化影响；
2. ESM mean pooling 对局部突变过于平滑，最近邻余弦相似度大量挤在 0.999 附近；
3. ESM 语义最近邻不等于实验轮次中的真实母本；
4. 单一内层 holdout 仍有结构选择方差；
5. 16 簇确有互补信号，但局部参考的泛化收益不足以稳定抵消噪声。

## 保留与拒绝

保留：

- train-only 局部参考构建器及自排除测试；
- position ranker 的可选 per-pair reference 编码；
- K=16 多分辨率父本模型与预注册融合脚本；
- 全部内外层诊断指标。

拒绝：

- 用 Stage 22 替换 Stage 21；
- 根据本次外层结果继续扫描权重；
- 把 ESM 最近邻称为真实母本。

## 下一阶段建议

1. 用 3–5 个训练内部 family folds 检验 K8/K16 权重稳定性；
2. 如果队友能提供父本、轮次或 lineage 元数据，建立真实 parent-child 差分；
3. 用 top-k 参考的软注意力替代单最近邻，并只在内层选择温度；
4. 使用残基级 ESM 或 IMGT 对齐后的关键位点表示，避免 mean pooling 稀释突变；
5. landscape1 单独建立重复测量噪声模型，它仍是总体分数的主要瓶颈。

## 产物

- 局部参考代码：`src/bioos_benchmark/esm_local_references.py`
- 局部参考测试：`tests/test_esm_local_references.py`
- 内层诊断：`artifacts/stage22/inner_local_reference_ensemble_diagnostic.json`
- 外层局部模型：`artifacts/stage22/outer_local_parent_delta_posconv/`
- 外层 K16 模型：`artifacts/stage22/outer_parent_conditioned_posconv_k16/`
- 预注册融合：`artifacts/stage22/preregistered_outer_multiresolution_parent_ensemble.csv`
- 指标：`artifacts/stage22/preregistered_outer_multiresolution_parent_ensemble.metrics.json`

大型 artifacts 为可再生产物，默认不提交 Git；代码、测试和阶段文档进入版本控制。
