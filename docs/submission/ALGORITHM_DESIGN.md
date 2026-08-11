# AbCompass 算法设计文档

## 技术摘要

AbCompass 是面向抗体候选亲和力排序的 ESM-2 150M 条件化位置卷积系统。当前正式版本为 Stage 21：在 `global_family_v2` 零精确重轻链跨折重叠、去重后 94,848 条外层验证记录上，Spearman 为 **0.462519**，Pearson 为 **0.480145**，Top-10 enrichment 为 **4.2276**。Stage 22 的局部参考候选外层为 0.462285，未替换正式版本。

模型目标是为同一可比较实验组中的抗体排序，不把输出解释为湿实验 KD，也不声称完成三维 de novo 结构设计。当前提交排除 VHH。

## 技术背景与改进价值

公开抗体数据混合 KD、IC50、EC50、binding、ADCC 和作者定义 fitness，且存在跨论文镜像数据与突变库重复。直接随机切分和跨 assay 回归会产生严重泄漏与量纲混淆。AbCompass 的改进重点不是简单增加参数，而是：

1. 在 `source × endpoint × antigen/assay` 内统一标签方向与排序目标；
2. 通过精确身份与 sequence-family 隔离评估家族外泛化；
3. 使用 ESM-2 150M 表示重链与轻链，定义 train-only 父本空间；
4. 用位置卷积保留突变位置，用父本差分表示相对变化；
5. 仅在外层训练集内部选择融合权重，外层只做一次确认。

## 数据流

```text
原始非 VHH 序列 CSV
  → 字段、单位、方向和可信等级审计
  → assay-safe comparison group
  → 精确重轻链去重与 family split
  → ESM-2 150M 重链/轻链冻结表示
  → train-only KMeans 父本簇、共识母本和 OOD
  → 绝对位置卷积 + 母本突变差分卷积
  → 组内 Smooth-L1 + pairwise ranking
  → 固定百分位秩集成
  → sequence_id、score、rank、heavy、light
```

## 输入与标签

必要输入字段：`record_id`、`heavy`、`light`、`source_file`、`task_route`、`comparison_group`、`score` 和 split。VHH 由轻链为空识别并排除。每个来源中的原始亲和力先校正“越大越好/越小越好”，再在可比较组内转换为 0–1 排序目标。

KD、IC50、EC50、二元 binding 和 ADCC 不共享同一物理主头。Stage 21 主模型路由为 `alphaseq_rank`。

## ESM-2 150M 表示

基座为 `facebook/esm2_t30_150M_UR50D`，固定 snapshot `a695f6045e2e32885fa60af20c13cb35398ce30c`。模型含 30 层 Transformer，隐藏维度 640。最后层有效残基均值为：

\[
e(x)=\frac{\sum_i m_i h_i^{(30)}}{\sum_i m_i}.
\]

重、轻链分别编码并连接为 \(e_{HL}=[e_H;e_L]\)。ESM 参数冻结，154,451 条唯一序列表示以 float16 缓存。完整原理见 `docs/ESM_TECHNICAL_GUIDE.md`。

## train-only 父本与 OOD

每个 assay 和重轻链长度组只用训练向量拟合 8 个 KMeans 簇：

\[
c(x)=\arg\min_k\lVert e_{HL}(x)-\mu_k\rVert_2^2.
\]

验证样本只分配到训练中心。簇内训练序列逐位置多数表决构造共识母本 \(r_c\)。到最近中心的距离相对于同簇训练距离转成经验百分位，作为 OOD 风险，不参与正式分数门控。

## 位置卷积与母本差分

绝对 token 通道表示当前残基。差分通道在残基未改变时为 0，否则编码有向突变对：

\[
\delta_i=\begin{cases}0,&x_i=r_{c,i},\\
\operatorname{pair}(r_{c,i},x_i),&x_i\ne r_{c,i}.
\end{cases}
\]

两个 embedding 连接后输入核宽 3 和 5 的一维卷积；展平表示与 assay/父簇条件 embedding 连接，再经 384、96 维 MLP 输出标量排序分数。

## 损失函数

\[
\mathcal L=\operatorname{SmoothL1}(s,y)+0.04\mathcal L_{rank},
\]

\[
\mathcal L_{rank}=\frac1{|P|}\sum_{(i,j)\in P}
\log\left(1+\exp[-\operatorname{sign}(y_i-y_j)(s_i-s_j)]\right).
\]

排序对只在同一 comparison group 内生成。优化器为 AdamW，初始学习率 `3e-4`，weight decay `2e-4`，cosine decay，梯度范数裁剪 1.0，验证 Spearman 早停。

## 固定集成

令 \(R\) 为平均百分位秩。正式模型为：

\[
S=0.775R(S_{17})+0.225[0.675R(S_{K8})+0.325R(S_\Delta)].
\]

等效权重：Stage 17 稳定模型 77.5%、K8 绝对父本 15.1875%、共识母本差分 7.3125%。权重只由外层训练内部的 family holdout 选择。

## 先进性与开源改进点

ESM-2、KMeans、CNN 与 AdamW 均为开源组件。我们的技术价值在于：双链 ESM 父本空间、train-only 共识母本、残基有向差分通道、assay-safe pairwise 约束、双层 family 验证和预注册融合。没有修改或冒充 ESM-2 的预训练权重；所有改进位于数据定义、下游架构和验证协议。

## 失败消融

Stage 22 将父本细化到 16 簇并加入同簇 ESM 最近训练参考。内层从 0.646403 提高到 0.648478，但外层从 0.462519 降至 0.462285。最近邻相似度普遍接近 0.999，却不代表真实实验谱系父本，因此候选未晋升。

## 能力边界

模型输出计算排序，不能证明真实 KD、表达性、中和能力、特异性或临床效果。旧 split 的 0.6683 含 39,272 条跨折完全相同抗体，只保留为历史结果。当前 0.462519 是内部严格验证，并非官方榜单保证。
