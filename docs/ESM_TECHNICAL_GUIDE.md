# ESM 技术原理：从蛋白质语言模型到抗体亲和力排序

## 1. ESM 是什么

ESM 是 Evolutionary Scale Modeling 的缩写，是一类在大规模蛋白质序列上预训练的 Transformer 蛋白质语言模型。我们当前使用的是：

- 模型：`facebook/esm2_t6_8M_UR50D`
- 参数量级：约 8M
- Transformer 层数：6
- 隐藏维度：320
- 固定 snapshot：`c731040fcd8d73dceaa04b0a8e6329b345b0f5df`

它的输入是一条氨基酸序列，输出是每个残基对应的上下文向量。ESM 本身不是亲和力计算器、不是 docking 工具，也不会直接输出 KD。它更像一个已经阅读过海量蛋白序列的通用序列编码器。

在 AbCompass 中，ESM 是特征提取主干；真正把特征转换为亲和力排序分数的是我们训练的抗体–抗原交互头。

## 2. ESM 解决什么问题

只用赛事监督数据从零训练 CNN，模型必须同时学习：

1. 什么样的氨基酸组合在蛋白中常见；
2. 哪些残基具有类似的结构或生化作用；
3. 局部 motif 如何影响上下文；
4. 相距很远的残基如何共同决定蛋白表示；
5. 哪些抗体和抗原组合可能对应更好的实验排序。

而亲和力监督数据远少于通用蛋白序列，当前严格模型实际使用约 24,559 条有抗原的 Gold+Silver 训练记录。从这些记录同时学会“蛋白语言”和“亲和力任务”很困难。

ESM 通过海量无标签蛋白序列预训练，提前学习前四类信息。下游训练只需要学习第五类任务映射：

\[
(e_H,e_L,e_G)\longrightarrow s
\]

其中：

- \(e_H\)：重链的 ESM 表示；
- \(e_L\)：轻链的 ESM 表示；
- \(e_G\)：抗原的 ESM 表示；
- \(s\)：候选排序分数。

这就是迁移学习：把通用蛋白知识迁移到抗体亲和力排序。

## 3. 蛋白质为什么能当作“语言”

自然语言由 token 构成，蛋白质序列由氨基酸残基构成。给定序列：

\[
x=(x_1,x_2,\ldots,x_L)
\]

每个 \(x_i\) 是 20 种标准氨基酸之一。氨基酸的意义依赖上下文，例如一个半胱氨酸是否可能参与二硫键，不能只由字符 `C` 自身决定，还与其位置和周围残基有关。

ESM 把每个 token 映射为可学习向量：

\[
h_i^{(0)}=E[x_i]+P_i
\]

其中 \(E[x_i]\) 是氨基酸 embedding，\(P_i\) 是位置信息。经过多层 Transformer 后得到上下文化表示：

\[
h_i^{(l+1)}=\operatorname{TransformerBlock}(h_1^{(l)},\ldots,h_L^{(l)})
\]

最终 \(h_i\) 不仅包含第 \(i\) 个氨基酸，还包含整条序列提供的上下文。

## 4. ESM 的预训练目标

ESM-2 的核心训练方式是 masked language modeling。随机遮住一部分氨基酸：

```text
原序列：EVQLVESGGGLVQPGGSLRLS
遮盖后：EVQLV[MASK]SGGLVQPGGSLRLS
```

模型根据其余上下文预测被遮住的残基。损失函数是被遮盖位置的交叉熵：

\[
\mathcal L_{MLM}
=
-\sum_{i\in M}\log p_\theta(x_i\mid x_{\setminus M})
\]

其中：

- \(M\) 是被遮盖位置集合；
- \(x_{\setminus M}\) 是可见上下文；
- \(p_\theta\) 是模型预测分布。

为了正确恢复残基，模型必须利用蛋白序列中的保守性、共现模式和长距离依赖。它没有被直接教授三维结构或亲和力，但这些任务相关规律会部分进入 embedding。

## 5. Self-attention 的数学原理

Transformer 的核心是 self-attention。给定当前层的残基矩阵：

\[
H\in\mathbb R^{L\times d}
\]

分别生成 query、key 和 value：

\[
Q=HW_Q,\qquad K=HW_K,\qquad V=HW_V
\]

注意力矩阵为：

\[
A=\operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}+M\right)
\]

输出为：

\[
Z=AV
\]

矩阵 \(A_{ij}\) 表示位置 \(i\) 在更新表示时对位置 \(j\) 的关注程度。因此一个 CDR 残基可以直接聚合远处框架残基的信息，不需要像卷积那样通过很多层逐步扩大感受野。

Multi-head attention 使用多组投影：

\[
\operatorname{MHA}(H)
=
\operatorname{Concat}(Z_1,\ldots,Z_m)W_O
\]

不同 attention head 可以学习不同类型的序列关系。

## 6. ESM embedding 如何进入 AbCompass

我们不使用 ESM 默认 pooler，因为加载器提示 pooler 参数没有来自预训练 checkpoint。我们使用最后一层残基表示，并按 attention mask 做均值池化。

对长度为 \(L\) 的有效残基：

\[
e
=
\frac{\sum_{i=1}^{L}m_i h_i}{\sum_{i=1}^{L}m_i}
\]

其中 \(m_i\in\{0,1\}\) 排除 padding。得到 320 维序列向量。

分别计算：

\[
e_H=\operatorname{ESM}(VH),\quad
e_L=\operatorname{ESM}(VL),\quad
e_G=\operatorname{ESM}(G)
\]

目前已经为 70,902 条唯一重链、轻链和抗原序列预计算并缓存 float16 embedding。缓存的好处是每次训练排序头不再重复运行 ESM。

## 7. 我们的 ESM 交互排序头

先将重链和轻链表示拼接并投影：

\[
a=\operatorname{GELU}(\operatorname{LN}(W_A[e_H;e_L]+b_A))
\]

将抗原投影到相同维度：

\[
g=\operatorname{GELU}(\operatorname{LN}(W_Ge_G+b_G))
\]

构建四组交互特征：

\[
z=[a;g;|a-g|;a\odot g]
\]

含义分别是：

- \(a\)：抗体本身的性质；
- \(g\)：抗原本身的性质；
- \(|a-g|\)：两个表示的差异；
- \(a\odot g\)：逐维匹配或共同激活。

排序分数为：

\[
s=\operatorname{MLP}(z)
\]

训练目标是来源加权 Smooth-L1：

\[
\mathcal L
=
\frac1N\sum_iw_i\operatorname{SmoothL1}(s_i,y_i)
\]

其中：

\[
w_i\propto n_{source(i)}^{-1/2}
\]

避免大数据源完全控制梯度。

## 8. ESM 与 CNN 是什么关系

### 相同点

二者都把可变长度氨基酸序列编码为固定维度向量，再由下游网络预测排序分数。

### CNN 的特点

CNN 使用局部卷积：

\[
h_i=\sigma\left(\sum_{j=-r}^{r}W_jx_{i+j}+b\right)
\]

优势：

- 速度快；
- 参数少；
- 擅长局部 motif；
- 适合从零训练和快速 baseline。

限制：

- 初始没有通用蛋白知识；
- 长距离依赖需要堆叠很多层；
- 只有约 2.5 万条任务数据时容易学到数据集特征而非蛋白规律。

### ESM 的特点

ESM 使用预训练 Transformer：

- 已从海量蛋白序列学习通用表示；
- self-attention 可直接建模长距离关系；
- 对未见家族通常更有优势；
- 计算与显存成本高于小型 CNN。

### 它们不是简单替代关系

当前路线是：

1. CNN 是轻量、独立、可快速训练的基线和潜在 ensemble 成员；
2. ESM 是更强的预训练特征主干；
3. 是否融合必须由固定 validation 验证，而不是默认“模型越多越好”。

CNN 可以捕捉任务数据中的局部突变 motif，ESM 可以提供通用蛋白上下文。若两者误差互补，秩集成可能进一步提升；若不互补，就只保留 ESM。

## 9. 冻结、部分微调和全量微调

### 冻结 ESM

当前做法是固定 ESM 参数 \(\theta_{ESM}\)：

\[
\nabla_{\theta_{ESM}}\mathcal L=0
\]

只更新排序头。优势是训练快、稳定、不易破坏预训练知识。

### 部分微调

下一步可以解冻最后一至两层：

\[
\theta=\{\theta_{head},\theta_{ESM,last}\}
\]

并采用分层学习率，例如排序头 \(3\times10^{-4}\)，ESM 层 \(10^{-5}\)。

### 全量微调

所有 ESM 参数更新，表达能力最高，但更容易过拟合，显存和训练成本也更高。对于当前 8M 模型和约 2.5 万条监督记录可以尝试，但必须严格早停。

## 10. 当前指标说明了什么

严格框架家族 validation：

| 模型 | Spearman | Pearson | Top-10 enrichment |
| --- | ---: | ---: | ---: |
| k-mer baseline | 0.1313 | 0.3444 | 1.4994 |
| 稀疏抗体–抗原交互 | 0.2102 | 0.4142 | 0.5363 |
| CNN 双模型秩集成 | 0.3780 | 0.4525 | 1.7472 |
| 冻结 ESM 交互头 | **0.4456** | **0.5268** | **2.4340** |
| ESM 65% + CNN 35% 秩集成 | **0.4571** | **0.5137** | **2.6750** |

ESM 相对 CNN 秩集成的 Spearman 提升为：

\[
0.4456-0.3780=0.0676
\]

相对提升约：

\[
\frac{0.4456-0.3780}{0.3780}\approx17.9\%
\]

Top-10 enrichment 2.434 表示预测前 10% 中真正优秀候选的富集程度约为随机选择的 2.43 倍。

这说明预训练表示显著改善了家族外泛化，但 0.4456 仍不是实验保证，也不能直接推导比赛名次。

## 11. ESM 是一个什么“工具”

从工程角度，ESM 包含三部分：

1. tokenizer：把氨基酸字符转换成 token ID；
2. pretrained encoder：把 token 序列转换成上下文化向量；
3. checkpoint：训练得到的参数文件。

它不是完整参赛系统。完整系统还需要：

- 数据治理；
- 抗体重链、轻链和抗原的输入组织；
- embedding 池化；
- 抗体–抗原交互头；
- 亲和力标签与损失函数；
- 防泄漏验证；
- 模型集成和 Rank 导出。

因此准确表述应是：

> AbCompass 使用 ESM-2 作为预训练蛋白序列编码器，并在其冻结表示上训练抗体–抗原交互排序头。

而不是：

> ESM 自动预测了抗体亲和力。

## 12. 下一步实验

1. 训练第二个固定数据 ESM 随机种子，验证稳定性。
2. 扫描 ESM–ESM 百分位秩集成。
3. 扫描 ESM 与 CNN 的融合，验证局部 motif 是否互补。
4. 解冻 ESM 最后 1–2 层做小学习率微调。
5. 如果 8M 模型收益稳定，再评估更大的 ESM-2 或抗体专用预训练编码器。

所有升级都必须在同一严格框架家族 validation 上超过当前结果，才能进入推荐提交模型。
