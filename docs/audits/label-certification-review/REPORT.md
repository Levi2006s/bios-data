# AbCompass 标签认证审计与模型升级建议

日期：2026-08-03  
审计对象：`抗体标签可信度认证表_修订版.docx`、`configs/label_registry.csv`、当前 framework-family benchmark 与阶段 6 验证预测。

## 技术结论

这份同学修订表值得采纳为“问题清单”，但不能未经原论文和实验单位复核就直接覆盖标签注册表。它指出了当前模型最重要的瓶颈：监督任务定义被 AbRank 的混合标签支配，问题严重程度高于是否使用更大的 ESM。

当前建议不是立即删除 17 万条记录，而是：

1. 拆分 AbRank 的原始 `Source`、终点和抗原比较组。
2. 将 KD、EC50/IC50、bind/no-bind、OVA 多反应性改为共享编码器上的不同任务头。
3. 建立来源宏平均、多折 out-of-fold 的模型选择指标。
4. 完成以上三项后再比较更大 ESM、结构特征和排序损失。

## 数据集和粒度

- DOCX：6 个 OOXML 表格，其中 1 个等级定义表、5 个文件认证明细表。
- 认证文件：83 个。
- 标签注册表：83 个文件，认证表连接覆盖率 83/83。
- 当前 benchmark：79 个有监督来源、1,352,114 条记录。
- 审计连接粒度：来源文件。
- 当前模型粒度：抗体重链、轻链、抗原序列组成的一条配对记录。

## 核心发现

### 1. 当前 0.4571 几乎由 AbRank 定义

当前 ESM 路径按每个来源最多 50,000 条抽样，保留 Gold/Silver 和存在抗原序列的记录：

| 划分 | 总记录 | AbRank | AbRank 占比 | 其他来源 |
| --- | ---: | ---: | ---: | ---: |
| 训练 | 24,559 | 24,126 | 98.24% | 433 |
| 验证 | 8,281 | 8,191 | 98.91% | 90 |

正式融合模型的拆分表现：

| 验证子集 | n | Spearman | Top-10 enrichment |
| --- | ---: | ---: | ---: |
| AbRank | 8,191 | 0.45895 | 2.67998 |
| 非 AbRank | 90 | 0.41186 | 0.00000 |
| 总体 | 8,281 | 0.45707 | 2.67502 |

因此 `0.45707` 仍是有效的 AbRank 主导验证结果，但不能解释为对 83 个文件或未知实验平台的广义亲和力能力。非 AbRank 只有 90 条，且拆到单个来源后多数不足 10 条，统计波动极大。

### 2. AbRank 的当前标签归一化不满足认证表的可比范围

同学表将 AbRank 亲和力等级标为 C/D，指出它混合 KD、IC50、escape 和排序值，需要拆分终点。当前原始文件还有 `Source` 字段，包含 RBD-escape、CATNAP、AlphaSeq、AbCoV、SKEMPIv2、AbSci、SabDab、OVA-binders 等来源。

BioOS 当前却把整个 `AbRank_dataset.csv` 设成一个 `comparison_group`，对全文件 `fitness` 统一计算百分位。不同终点、单位、抗原和来源由此进入同一个标量秩，模型可能学到数据来源或抗原类别捷径，而不是真正的结合规律。

严重程度：**Critical**。置信度：**高**。影响：169,130 条完整 benchmark 记录；在当前抽样训练/验证中分别影响 24,126/8,191 条。

建议修正：

- 从原始 `Source`、KD/IC50/escape 字段识别终点。
- `comparison_group = source_file + Source + endpoint + antigen_id/assay`。
- 主亲和力头优先使用可确认 KD/pKD 的记录。
- IC50、escape、OVA 等只进入对应辅助任务。
- 对修正前后标签的一致性和秩反转率做自动测试。

### 3. 功能终点不应作为无条件 KD 回归标签

认证表识别出 16 个仍被当前注册表列为 Gold 的 EC50/IC50/ADCC 文件，共 935 条 benchmark 记录。包括 Kothiwal 的 EC50、Rawat/Shanker 的 IC50，以及 ADCC EC50。

这些指标并非“坏数据”，但回答的是不同问题：

- KD/pKD：平衡结合亲和力。
- EC50：达到半最大响应所需浓度，受表达、效价和实验体系影响。
- IC50：抑制或中和效力，受机制、化学计量和细胞体系影响。
- ADCC EC50：效应细胞、靶细胞密度、Fc 功能等共同决定。

严重程度：**High**。置信度：**高**。

建议修正：共享 ESM 编码器，但使用 `KD ranking head`、`EC50/IC50 functional head` 和必要的 assay embedding。只有与目标任务匹配的头参与正式排序；功能头作为正则化或复赛开发性能力。

### 4. 两个 OVA 文件的开发价值方向与当前目标相反

认证表将 `makowski2022cooptimization_iso_ova.csv` 和 `...igg_ova.csv` 解释为非特异性/多反应性结合：原始 assay 信号越大表示 OVA 结合越强，但开发价值通常越低。当前注册表把四个 ANT/OVA 文件统一设置为 `direction=+1`、Silver、监督可用。

严重程度：**High**。置信度：**中高**。影响：222 条记录。

正确处理不是篡改原始 assay 含义：

- 原始 OVA 信号仍保留“越大=结合越强”。
- 在综合开发目标中，将 OVA 作为负向风险或最小化目标。
- ANT 目标结合与 OVA 非特异结合必须使用不同任务标识。

### 5. 大规模弱标签已有部分正确防护

Li 2023 与 Engelhart 2022 的 AlphaSeq/模型校准标签在认证表中为 B/C。当前注册表已将其设为 `model_predicted + Weak`，阶段 6 ESM 只训练 Gold/Silver，因此不会被数百万预测标签直接淹没。这一策略应保留。

这些数据可以用于：

- 自监督或对比预训练。
- 低权重辅助头。
- 教师–学生蒸馏，但必须与实验 Gold 验证隔离。

不应直接用于：

- 主验证集。
- 与 SPR/BLI 等权的连续亲和力监督。

## 推荐模型结构

建议把 AbCompass 改为质量感知多任务排序模型：

```text
heavy / light / antigen
          │
      ESM encoder
          │
 antibody–antigen interaction representation
          │
  ┌───────┼──────────┬───────────┐
  │       │          │           │
 KD rank  EC50/IC50  bind class  OVA risk
  head     head        head        head
```

总损失可写为：

$$
\mathcal L =
\lambda_{KD}\mathcal L_{rank}
+ \lambda_F\mathcal L_{functional}
+ \lambda_B\mathcal L_{binary}
+ \lambda_R\mathcal L_{risk},
$$

其中每条记录只更新有标签的任务头。再乘以质量和来源权重：

$$
w_i = w_{quality(i)}\,n_{source(i)}^{-\alpha}\,w_{censor(i)}.
$$

建议初始质量权重只作为可验证超参数，而不是定论，例如 A=1.0、B=0.6、C=0.2、D=0；通过 out-of-fold 选择，而不是凭直觉固定。

## 新的评估标准

主模型选择不应继续只看全局 micro Spearman。至少同时报告：

1. KD-only global Spearman。
2. macro-source Spearman：每个可评估来源先算 Spearman，再等权平均。
3. macro-antigen Spearman。
4. 多折 family-safe out-of-fold 均值、标准差和最差折。
5. Top-10 enrichment 及其来源组 bootstrap 区间。
6. 功能终点和 OVA 风险作为独立指标，不混入 KD 主分数。

晋升门槛建议同时满足：KD 主指标提高、macro-source 不下降、最差折不明显恶化。单一验证集上小于 0.002 的变化不应直接晋升。

## 实施优先级

| 优先级 | 改动 | 预期收益 | 风险 |
| --- | --- | --- | --- |
| P0 | AbRank 按 Source/终点/抗原拆组 | 最大限度降低主标签混杂 | 需要重建 benchmark 和全部基线 |
| P0 | KD/功能/分类/风险多任务 | 利用数据而不混淆语义 | 训练和评估代码复杂度增加 |
| P0 | 来源宏平均与多折 OOF | 防止单来源支配模型选择 | 训练成本增加 |
| P1 | A/B/C/D 连续置信加权 | 利用异质质量信息 | 权重可能再次过拟合 |
| P1 | CDR-aware/learned pooling | 聚焦结合相关区域 | 需与正确标签任务一起验证 |
| P2 | ESM-2 35M/150M 或结构模型 | 提高表征容量 | 若标签未修复，会放大捷径学习 |

## 不确定性与开放问题

- 同学表包含“AI 建议”和“待复核”，不是原论文证据的替代品。
- 171,296 是至少命中一种冲突的去重来源记录数；各问题类别有重叠，不能相加。
- 初赛官方最终标签若本身就是跨终点统一秩，训练目标仍需贴合官方定义，但应保留 assay 条件特征并做分层验证。
- 需要进一步核验 AbRank `fitness` 的构建过程、各 Source 的单位和 `Aff_op` 删失符号。
- 若能获得 SPR/BLI 的 kon、koff、拟合质量和重复实验，可进一步做异方差或删失排序模型。

## 可复核证据

- 原始 DOCX：`抗体标签可信度认证表_修订版.docx`
- OOXML 表格抽取：`artifacts/label_audit/certification_tables.tsv`
- 逐文件核对：`artifacts/label_audit/reconciliation.csv`
- 汇总统计：`artifacts/label_audit/summary.json`
- 解析脚本：`scripts/extract_docx_tables.py`
- 审计脚本：`scripts/audit_label_certification.py`
- 规范化报告载荷：`docs/audits/label-certification-review/artifact.json`

HTML 报告未生成：当前运行环境缺少 Node.js，官方 portable artifact 打包器无法启动。完整规范化载荷已保留，可在具备 Node.js 的环境中重新执行打包。
