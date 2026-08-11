# ESM 技术原理与 AbCompass 实现指南

> 面向队友的当前版本（Stage 22，2026-08-05）。本文区分“ESM 本身”“我们的下游模型”和“实验验证”，并以当前无泄漏主线为准。

## 1. 一句话说明

ESM（Evolutionary Scale Modeling）是一个在海量蛋白质序列上预训练的 Transformer 编码器。它把氨基酸序列变成有上下文的数值向量，但它本身不输出 KD、IC50 或比赛排名。

AbCompass 使用 ESM-2 表示抗体重链和轻链，再由我们训练的位置卷积、父本条件化和排序集成模型输出亲和力优先级。因此它不是 Qwen，也不是把序列交给通用聊天模型；当前主干是蛋白质语言模型 ESM-2。

## 2. 当前到底使用哪个 base model

当前全量主线使用：

| 项目 | 当前值 |
|---|---|
| Hugging Face 模型 | `facebook/esm2_t30_150M_UR50D` |
| 参数量 | 约 150M |
| Transformer 层数 | 30 |
| 隐藏维度 | 640 |
| 固定 snapshot | `a695f6045e2e32885fa60af20c13cb35398ce30c` |
| 当前用法 | 冻结编码、最后层 residue mean pooling、float16 缓存 |
| 当前缓存 | 154,451 条唯一序列，640 维 |
| 训练硬件 | NVIDIA GeForce RTX 4090 24 GB |

8M（6 层、320 维）和 35M 版本是阶段 6–10 的历史容量消融，不再是当前最佳主干。保留它们是为了复现实验，不应再向队友表述为“当前 base model”。

## 3. ESM 是什么工具，不是什么工具

ESM 工程上由三部分组成：

1. tokenizer：把 `EVQL...` 等氨基酸字符变成 token ID；
2. Transformer encoder：为每个残基产生上下文化向量；
3. checkpoint：预训练得到的权重。

ESM 擅长提供序列的通用蛋白语义：保守模式、局部 motif、上下文依赖，以及部分与结构相关的统计信号。

ESM 不是：

- 大语言对话模型；
- 抗体–抗原 docking；
- 三维复合物预测器；
- 直接的 KD/IC50 仪器；
- 自动保证实验成功的黑盒。

准确说法是：

> AbCompass 以冻结的 ESM-2 150M 作为蛋白序列表征器，并在严格无泄漏数据上训练抗体排序模型。

## 4. 为什么蛋白质可以看成一种“语言”

设蛋白序列为

\[
x=(x_1,x_2,\ldots,x_L),\qquad x_i\in\mathcal A,
\]

其中 \(\mathcal A\) 是氨基酸字母表。一个残基的作用依赖上下文：同一个 `C` 在不同位置可能参与二硫键，也可能只是普通局部残基。模型先把 token 与位置编码相加：

\[
h_i^{(0)}=E(x_i)+P_i.
\]

经过 30 层 Transformer 后：

\[
H^{(l+1)}=\operatorname{TransformerBlock}(H^{(l)}),
\]

最终 \(h_i^{(30)}\) 同时表达当前位置和全序列上下文。

## 5. ESM-2 如何预训练

核心目标是 masked language modeling。随机遮盖位置集合 \(M\)，让模型从其余残基恢复原字符：

\[
\mathcal L_{MLM}
=-\sum_{i\in M}\log p_\theta(x_i\mid x_{\setminus M}).
\]

为了恢复被遮盖残基，模型必须学习哪些残基组合合理、哪些位置保守、远距离位置如何共同约束序列。它没有直接看我们的亲和力标签，因此不会天然知道某个抗体的 KD；亲和力映射仍需赛事监督数据训练。

## 6. Self-attention 数学原理

给定残基矩阵 \(H\in\mathbb R^{L\times d}\)：

\[
Q=HW_Q,\qquad K=HW_K,\qquad V=HW_V,
\]

\[
A=\operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}+M_{mask}\right),
\qquad Z=AV.
\]

\(A_{ij}\) 表示更新位置 \(i\) 时对位置 \(j\) 的关注强度。多头注意力并行学习多种关系：

\[
\operatorname{MHA}(H)=\operatorname{Concat}(Z_1,\ldots,Z_m)W_O.
\]

这使一个 CDR 残基可以直接汇集远处框架残基的信息，而不必像浅层卷积那样逐层扩大感受野。但 attention 权重不等于实验因果解释，也不能直接当成表位证据。

## 7. 从 residue embedding 到序列 embedding

当前缓存取最后一层有效残基均值：

\[
e(x)=\frac{\sum_{i=1}^{L}m_i h_i^{(30)}}{\sum_{i=1}^{L}m_i},
\qquad e(x)\in\mathbb R^{640},
\]

其中 \(m_i\) 排除 padding 和特殊 token。重链与轻链分别编码：

\[
e_H=e(V_H),\qquad e_L=e(V_L),\qquad e_{HL}=[e_H;e_L].
\]

阶段 15 的严格外层结果证明轻链不能省略：只用重链的 ESM150 单模 Spearman 为 0.382527，重链+轻链为 0.395231，提高约 0.0127。

均值池化的优点是稳定、快速、可缓存；缺点是可能稀释少数关键突变的位置效应。这正是 ESM 与位置卷积互补，而不是 ESM 完全替代 CNN 的原因。

## 8. ESM 与 CNN 的关系

CNN 的一维局部卷积可写作：

\[
c_i=\sigma\left(\sum_{j=-r}^{r}W_j E(x_{i+j})+b\right).
\]

它参数较少、训练快，特别擅长捕获“某个对齐位置附近发生了什么突变”。ESM 的 Transformer 已在大规模蛋白序列上预训练，更擅长通用上下文与长距离依赖，但全局均值会压缩位置信息。

AbCompass 当前不是二选一，而是分工：

- ESM150：定义通用连续序列空间、父本家族和 OOD 距离；
- position-preserving CNN：保留每个重链/轻链位置的突变模式；
- 条件 embedding：告诉 CNN 当前属于哪个 assay、长度组和 ESM 父簇；
- 秩集成：组合不同模型的互补顺序。

所以“模型是 ESM 还是 CNN”的答案是：**base representation 是 ESM-2 150M，最终排序器是 ESM 条件化的位置卷积多模型系统。**

## 9. ESM 在当前系统中的六种作用

### 9.1 冻结特征编码

154,451 条唯一序列只需计算一次 640 维 float16 表示。训练下游头时不反复运行 150M 参数主干，显著节约 GPU 时间并保持实验可比。

### 9.2 双链表示

重链与轻链共同定义抗体。当前对二者分别编码并连接，不再沿用早期遗漏轻链的单链实现。

### 9.3 train-only 父本聚类

在每个 assay 与重轻链长度组内，只用训练样本的 ESM 向量拟合 KMeans。设训练中心为 \(\mu_1,\ldots,\mu_K\)，样本分配为：

\[
c(x)=\arg\min_k\lVert e_{HL}(x)-\mu_k\rVert_2^2.
\]

验证样本只允许分配到训练中心，不能参与拟合。Stage 18 的 \(K=8\)（4 个组共 32 个簇）是当前正式父本分辨率；Stage 22 增加 \(K=16\) 作为细粒度互补模型。

### 9.4 连续 OOD 不确定性

定义到最近训练中心的距离：

\[
d(x)=\min_k\lVert e_{HL}(x)-\mu_k\rVert_2.
\]

再相对于同组训练距离经验分布转为百分位：

\[
q(x)=\frac{1}{|T_g|}\sum_{t\in T_g}\mathbf 1[d(t)\le d(x)].
\]

\(q(x)\) 越高，样本离训练分布越远。H119/L115 组约 30.45% 验证唯一序列超过训练距离第 90 百分位，远域桶 Spearman 只有约 0.216。这个量目前用于风险标记，不参与调分，因为 Stage 20 的 OOD 门控没有可靠提高总分。

### 9.5 共识母本与突变差分

在每个 train-only 父簇中，对每个对齐位置取训练序列多数残基，得到共识参考 \(r_c\)。当前序列为 \(x\) 时，差分 token 为：

\[
\delta_i=
\begin{cases}
0,&x_i=r_{c,i},\\
\operatorname{pair}(r_{c,i},x_i),&x_i\ne r_{c,i}.
\end{cases}
\]

模型同时看绝对 token \(x_i\) 与差分 token \(\delta_i\)，从而区分“这个位置是什么”和“它相对母本发生了什么”。Stage 21 正式模型就是绝对父簇模型与共识差分模型的融合。

### 9.6 局部 ESM 近邻参考（Stage 22 消融）

为了避免一个簇只有一个粗共识，Stage 22 在同一训练簇内为样本找 ESM 最近参考：

\[
r^*(x)=\arg\max_{r\in T_{c(x)}}
\frac{e_{HL}(x)^\top e_{HL}(r)}{\lVert e_{HL}(x)\rVert\lVert e_{HL}(r)\rVert}.
\]

训练样本检索时强制 \(r\ne x\)，验证样本只能检索训练样本。然后用 \(r^*(x)\) 替代共识构造突变对。

这个想法在内层融合从 0.646403 小幅提高，但外层预注册融合未超过 Stage 21。原因是 ESM 均值向量的最近邻相似度普遍接近 1，却未必是真实实验母本；“蛋白语言上相似”不等价于“实验谱系上的父本”。因此它作为消融和未来软多父本注意力的起点保留，不进入当前推荐提交模型。

## 10. 最终排序头的数学结构

位置模型分别嵌入重链、轻链及可选突变差分 token，经过一维卷积和池化得到抗体表示 \(a\)。同时加入 assay、长度和父簇条件向量 \(u\)：

\[
a=\operatorname{Pool}\bigl(\operatorname{Conv1D}([E(x);E_\Delta(\delta)])\bigr),
\]

\[
s=f_\phi([a;u]).
\]

训练目标以鲁棒回归为主，并加入同一可比较组内的 pairwise 排序约束：

\[
\mathcal L=\mathcal L_{SmoothL1}+\lambda\mathcal L_{rank},
\]

\[
\mathcal L_{rank}=\frac1{|P|}\sum_{(i,j)\in P}
\log\left(1+\exp[-\operatorname{sign}(y_i-y_j)(s_i-s_j)]\right).
\]

当前 \(\lambda=0.04\)。配对只发生在同一 comparison group，避免把不同 assay 或不同终点强行比较。

## 11. 当前正式模型如何集成

各组件先转为平均秩百分位 \(R(\cdot)\)，Stage 21 固定公式为：

\[
S=0.775R(S_{17})+0.225\left[0.675R(S_{K8})+0.325R(S_{\Delta})\right].
\]

等效权重：

- Stage 17 稳定主模型：77.5%；
- 8 簇绝对父本模型：15.1875%；
- 共识母本差分模型：7.3125%。

这些权重先在外层训练集内部的二级 family holdout 选择，随后外层验证只评估一次，没有看外层分数再调权。

Stage 22 试验加入局部参考与 16 簇模型，内层从 0.646403 到 0.648478，但预注册外层为 0.462285，低于 Stage 21 的 0.462519，故未晋升。

## 12. 防泄漏设计

当前分割 `global_family_v2_split` 满足精确重轻链对跨 fold 重叠为 0；验证集按生物学唯一序列去重后为 94,848 条。旧 `framework_family_split` 后来发现 39,272 个训练—验证完全相同抗体序列，其 0.6683 只能作为历史开发分，不能与当前严格结果直接比较。

所有 ESM 派生操作遵守：

1. 聚类中心只拟合训练 embedding；
2. 共识母本只统计训练序列；
3. 验证近邻只从训练候选中检索；
4. 训练近邻排除自身；
5. OOD 经验分布只由训练距离定义；
6. 结构和权重在内层 holdout 选择，外层只做确认；
7. ESM embedding 可看验证序列本身，因为它是无标签确定性编码，但绝不读取验证标签或让验证参与训练统计量。

## 13. 冻结、部分微调与全量微调

当前主线冻结 ESM：

\[
\nabla_{\theta_{ESM}}\mathcal L=0,
\]

只训练下游排序器。优点是稳定、显存可控、可缓存，并降低在高度重复实验数据上破坏预训练知识的风险。

历史上已尝试局部残基层微调和池化消融，但没有稳定成为当前最佳。未来若解冻最后若干层，应使用较小学习率：

\[
\eta_{head}\approx3\times10^{-4},\qquad
\eta_{ESM}\approx10^{-6}\sim10^{-5},
\]

并在多个内层 family fold 上验证。不能只因训练损失下降就认为微调有效。

## 14. 指标应如何解读

以下均为当前严格 `global_family_v2` 外层、去重后 94,848 条验证记录，彼此可比：

| 阶段 / 模型 | Spearman | 说明 |
|---|---:|---|
| Stage 15 ESM150 重链+轻链单模 | 0.395231 | 冻结 ESM 全局表示 |
| Stage 18 8 簇父本位置卷积单模 | 0.452528 | ESM 定义父本条件 |
| Stage 21 当前正式融合 | **0.462519** | 绝对序列 + 共识突变差分 |
| Stage 22 16 簇单模 | 0.447547 | 单模强于共识差分，但需融合 |
| Stage 22 预注册融合 | 0.462285 | 未超过 Stage 21，拒绝晋升 |

当前正式模型其他指标：Pearson 0.480145，Top-10 enrichment 4.2276；landscape1 Spearman 0.275867，landscape2 0.656478。

Top-10 enrichment 4.23 表示预测前 10% 对真实高分候选的富集约为随机选择的 4.23 倍，不表示前 10% 有 423% 的绝对成功率。Spearman 0.4625 是内部严格验证分，不是官方 leaderboard 分，也不能保证比赛名次。

Stage 21 相对 Stage 18 只提高 0.000310。按 22,513 个精确抗体对做 500 次配对 bootstrap，候选胜率 97.2%，但 95% 区间下界略低于 0，所以应表述为“谨慎晋升的小幅增益”。

## 15. 为什么没有达到 0.8 或 0.9

主要不是 GPU 不够，而是验证任务发生了变化：当前严格分割要求泛化到未见 family，并移除了重复抗体泄漏。landscape1 还混合多个母本，重复测量存在噪声，其同序列均值经验上限约 0.699；在这一口径下宣称 0.8–0.9 并不诚实。

旧分割的 0.6683 含 39,272 条完全相同序列跨 fold，不能作为新模型目标。提高可信成绩需要新增可泛化信息，而不是继续在同一外层验证上扫权重。

## 16. 当前能力边界

模型能够：

- 为同一 assay 中的候选抗体生成亲和力优先顺序；
- 使用重链、轻链、父本上下文和实验条件；
- 标记 ESM 空间中的远分布候选；
- 在严格 family 隔离条件下给出可复现评估；
- 富集值得优先湿实验验证的候选。

模型不能直接保证：

- 真实 KD 数值；
- 表达、稳定性、免疫原性或中和能力；
- 新抗原/新表位上的可靠性；
- ESM 相似度对应真实实验母本；
- 当前内部成绩对应某个官方排名。

## 17. 拿第一的优先升级路线

优先级按预期收益与科学可信度排序：

1. **拿到真实母本/轮次元数据。** 用实验谱系替代均值 ESM 最近邻，这是 Stage 22 暴露的最大信息缺口。
2. **软多父本注意力。** 不选单一最近邻，而对同簇多个训练参考按可学习权重聚合，并限制权重只依赖训练信息。
3. **残基级 ESM 与对齐。** 缓存关键层 residue embedding，结合 IMGT/CDR 编号，用交叉注意力或低秩适配器保留突变位置。
4. **多内层 family fold。** 当前只有一个二级 holdout，下一步至少 3–5 folds，按平均增益和方差选结构。
5. **抗原与表位信息。** 当前主 AlphaSeq 路线主要是抗体 landscape；若比赛输入含可靠抗原/表位，应加入抗体–抗原 residue interaction，而非只做抗体侧排序。
6. **标签噪声模型。** 显式建模重复测量方差、来源偏差和 censored KD，比简单平均更有希望改善 landscape1。
7. **结构信息。** 在规则允许且计算可承受时加入抗体结构、表面可及性和界面先验，但必须在 family 外验证证明收益。

Stage 22 的结论不是“路线失败”，而是把下一步从“再加一个最近邻模型”收敛为“真实谱系、残基级表示和多折稳定选择”。

## 18. 复现入口

- ESM150 缓存：`artifacts/stage14/esm150_full_alphaseq_embeddings.pt`
- 父本聚类：`src/bioos_benchmark/esm_parent_clusters.py`
- 局部参考：`src/bioos_benchmark/esm_local_references.py`
- 位置/差分模型：`src/bioos_benchmark/positional_neural_ranker.py`
- Stage 21 正式融合：`scripts/build_stage21_preregistered_outer_ensemble.py`
- Stage 22 预注册融合：`scripts/build_stage22_preregistered_outer_ensemble.py`
- 阶段报告：`docs/stage21/` 与 `docs/stage22/`

所有正式结论以保存的 metrics JSON 和阶段报告为准；可再生的大型模型、embedding 与预测位于 `artifacts/`，默认不提交 Git。
