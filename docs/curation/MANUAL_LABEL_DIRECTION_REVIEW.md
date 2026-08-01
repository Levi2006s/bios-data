# 人工标签方向审核表

> 用途：请团队成员逐文件审核标签的含义、单位和方向。此表只处理数据定义，不涉及模型训练。

## 一、审核结论摘要

- 登记文件：83 个；
- `+1`（数值越大越好）：49 个；
- `-1`（数值越小越好）：33 个；
- `0`（没有监督标签）：1 个；
- 数据等级：Gold 74 个、Silver 5 个、Weak 3 个、Auxiliary 1 个。

## 二、统一判断规则

| 标签形式 | 正确方向 | 简单解释 |
|---|---:|---|
| 原始 KD/Kd | -1 | 解离常数越小，抗体与抗原结合越强 |
| `log10(KD)` | -1 | 对 KD 取对数后仍然是越小越好 |
| `-log10(KD)` / pKD | +1 | 加了负号，所以数值越大代表 KD 越小 |
| IC50 / EC50 | -1 | 达到一半效果所需浓度越小越好 |
| binder=1, non-binder=0 | +1 | 1 表示能够结合 |
| 实验结合信号/富集度 | +1 | 只在论文确认信号越大代表结合越强时使用 |
| 预测 `log10 KD(nM)` | -1 | 是模型预测的 KD，只作为 Weak 标签 |

## 三、请优先审核的项目

1. **来源 4 AbRank**：CSV 的 `fitness` 等于 `log10(KD/IC50)`，应为 `-1`，不是旧程序猜测的 `+1`。
2. **来源 9 连续 KD 文件**：字段名写 `Kd [M]`，但论文和值域 3.3–2946.89 表明应按 nM 理解；方向仍为 `-1`。
3. **来源 3 和 6**：`Pred_affinity` 是预测的 `log10 KD(nM)`，方向为 `-1`，等级为 Weak。
4. **来源 12**：是相对 ANT/OVA binding signal，方向为 `+1`，但不是绝对 KD，因此列为 Silver。
5. **来源 17**：原始 KD 方向为 `-1`；3 条零值或明显不合理数值已进入隔离，不参与普通监督数据。

审核时若不同意某项，请直接在对应表格最后一列填写建议，例如：`改为 +1，原因：论文第 X 页……`。

## 四、逐文件审核表

### 初赛-序列数据/1

论文：Assessment and incorporation of in vitro correlates to pharmacokinetic outcomes in antibody developability workflows（2024）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `jain2024assessment_Hen_Lys_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `jain2024assessment_mouse_Ly_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/2

论文：Unlocking de novo antibody design with generative artificial intelligence（2023）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `shanehsazzadeh2023unlocking_adcc_ec50.csv` | `fitness` | EC50；pM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanehsazzadeh2023unlocking_kd_hher2_fab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanehsazzadeh2023unlocking_kd_hher2_mab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanehsazzadeh2023unlocking_zerokd_trastuzumab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/3

论文：Machine learning optimization of candidate antibody yields highly diverse sub-nanomolar affinity antibody libraries（2023）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `li2023machine_scFv-SARS-CoV-2_affinity1.csv` | `Pred_affinity` | predicted_log10_KD；log10(nM) | -1（越小越好） | model_predicted | Weak | paper Fig. 1/2 identifies predicted affinity as log10 KD in nM; CSV values match；group 6 reproduces the labeled subset used to construct group 3 | □ 同意 / □ 修改： |
| `li2023machine_scFv-SARS-CoV-2_affinity2.csv` | `Pred_affinity` | predicted_log10_KD；log10(nM) | -1（越小越好） | model_predicted | Weak | paper Fig. 1/2 identifies predicted affinity as log10 KD in nM; CSV values match；group 6 reproduces the labeled subset used to construct group 3 | □ 同意 / □ 修改： |

### 初赛-序列数据/4

论文：AbRank: A Benchmark Dataset and Metric-Learning Framework for Antibody-Antigen Affinity Ranking（2025）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `AbRank_dataset.csv` | `fitness` | log10_KD_or_IC50；log10(nM or source assay unit) | -1（越小越好） | experimental | Silver | CSV log_Aff/fitness equals log10 affinity (e.g. 815 nM -> 2.9112); AbRank paper treats stronger binding as preferred；heterogeneous assays and units; compare only within compatible antigen/assay groups | □ 同意 / □ 修改： |

### 初赛-序列数据/5

论文：Measuring the sequence-affinity landscape of antibodies with massively parallel titration curves（2017）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `adams2017measuring_4420-fluorescein_kd-flow.csv` | `fitness` | KD；M | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `adams2017measuring_4420-fluorescein_kd-titeseq.csv` | `fitness` | KD；M | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |

### 初赛-序列数据/6

论文：A dataset comprised of binding interactions for 104,972 antibodies against a SARS-CoV-2 peptide（2022）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `engelhart2022dataset_scFv-SARS-CoV-2_affinity.csv` | `fitness` | predicted_log10_KD；log10(nM) | -1（越小越好） | model_predicted | Weak | paper Fig. 1/2 identifies predicted affinity as log10 KD in nM; CSV values match；group 6 reproduces the labeled subset used to construct group 3 | □ 同意 / □ 修改： |

### 初赛-序列数据/7

论文：Efficient evolution of human antibodies from general protein language models（2023）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `hie2023efficient_CoV2Beta_C143_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_CoV2Beta_REGN10987_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_CoV2_S309_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_CoV2omicron_REGN10987_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_MEDIUCA_H1Solomon_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_MEDIUCA_H4Hubei_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_MEDI_H4Hubei_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_MEDI_H7HK16_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hie2023efficient_ebola_mab114_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/8

论文：Toward enhancement of antibody thermostability and affinity by computational design in the absence of antigen（2023）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `hutchinson2023enhancement_multikd_fab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_multikd_igg.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_singlekd_fab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_singlekd_igg.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_top200kd_fab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_top200kd_igg.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_top27kd_fab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `hutchinson2023enhancement_top27kd_igg.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/9

论文：Retrospective SARS-CoV-2 human antibody development trajectories are largely sparse and permissive（2024）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `kirby2024retrospective_ab-SARSCoV2_binary_kd.csv` | `KD [bind/no bind]` | binding_class；0/1 | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kirby2024retrospective_ab-SARSCoV2_kd.csv` | `Kd [M]` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；exported header says M but paper/value scale is nM; zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |

### 初赛-序列数据/10

论文：Mutational landscape of antibody variable domains reveals a switch modulating interdomain dynamics and antigen binding（2017）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `koenig2017mutational_kd_g6.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/11

论文：High-Throughput Machine Learning-Aided Antibody Discovery for Cell Surface Antigens（2025）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `kothiwal2025htp_DCC_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_DCC_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_DKK_1.00_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_DKK_1.00_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_IL23R_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_IL23R_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_LOX1_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_LOX1_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_PDL1_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_PDL1_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_PDL2_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_PDL2_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_ROBO1_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_ROBO1_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_ROBO2N_hROBO2N_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_ROBO2N_hROBO2N_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_Syncytin2_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_Syncytin2_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_TIGIT_ec50.csv` | `fitness` | EC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `kothiwal2025htp_TIGIT_spr.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/12

论文：Co-optimization of therapeutic antibody affinity and specificity using machine learning（2022）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `makowksi2022cooptimization_iso_ant.csv` | `fitness` | binding_signal；source-normalized signal | +1（越大越好） | experimental | Silver | supplied paper plus original CSV measurement column；ANT/OVA binding is a relative assay signal, not an absolute KD | □ 同意 / □ 修改： |
| `makowski2022cooptimization_igg_ant.csv` | `fitness` | binding_signal；source-normalized signal | +1（越大越好） | experimental | Silver | supplied paper plus original CSV measurement column；ANT/OVA binding is a relative assay signal, not an absolute KD | □ 同意 / □ 修改： |
| `makowski2022cooptimization_igg_ova.csv` | `fitness` | binding_signal；source-normalized signal | +1（越大越好） | experimental | Silver | supplied paper plus original CSV measurement column；ANT/OVA binding is a relative assay signal, not an absolute KD | □ 同意 / □ 修改： |
| `makowski2022cooptimization_iso_ova.csv` | `fitness` | binding_signal；source-normalized signal | +1（越大越好） | experimental | Silver | supplied paper plus original CSV measurement column；ANT/OVA binding is a relative assay signal, not an absolute KD | □ 同意 / □ 修改： |

### 初赛-序列数据/13

论文：Binding affinity landscapes constrain the evolution of broadly neutralizing anti-influenza antibodies（2021）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `phillips2021binding_cr6261_h1_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `phillips2021binding_cr6261_h9_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `phillips2021binding_cr9114_h1_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `phillips2021binding_cr9114_h3_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/14

论文：Ab-CoV: binding affinity and neutralization profiles of coronavirus-related antibodies（2022）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `rawat2022abcov_ic50.csv` | `fitness` | IC50；source unit | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `rawat2022abcov_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/15

论文：Automated optimisation of solubility and conformational stability of antibodies and proteins（2023）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `rosace2023automated_kd_adalimumab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `rosace2023automated_kd_golimumab.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/16

论文：IgDesign: in vitro validated antibody design using inverse folding（2024）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `shanehsazzadeh2024igdesign_Afasevikumab-IL17A_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanehsazzadeh2024igdesign_Bimagrumab-ACVR2B_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanehsazzadeh2024igdesign_Eculizumab-C5_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanehsazzadeh2024igdesign_Osocimab-FXI_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanehsazzadeh2024igdesign_Spesolimab-IL36R_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanehsazzadeh2024igdesign_Tezepelumab-TSLP_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanehsazzadeh2024igdesign_Utomilumab-TNFRSF9_kd.csv` | `fitness` | KD；nM | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |

### 初赛-序列数据/17

论文：Unsupervised evolution of protein and antibody complexes with a structure-informed language model（2024）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `shanker2024unsupervised_Ly1404-BQ.1.1_IC50.csv` | `fitness` | IC50；ng/uL | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanker2024unsupervised_Ly1404-BQ.1.1_Kd.csv` | `fitness` | KD；M | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanker2024unsupervised_Ly1404_Wuhan_IC50.csv` | `fitness` | IC50；ng/uL | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanker2024unsupervised_SA58-BA.1_IC50.csv` | `fitness` | IC50；ng/uL | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanker2024unsupervised_SA58-BQ.1.1_IC50.csv` | `fitness` | IC50；ng/uL | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |
| `shanker2024unsupervised_SA58-BQ.1.1_Kd.csv` | `fitness` | KD；M | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |
| `shanker2024unsupervised_SA58-XBB.1.5_Kd.csv` | `fitness` | KD；M | -1（越小越好） | experimental | Gold | supplied paper plus original CSV measurement column；zero and physically implausible values are quarantined, not silently clipped | □ 同意 / □ 修改： |

### 初赛-序列数据/18

论文：AVIDa-hIL6: a large-scale VHH interaction dataset（2023）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `tsuruta2024avida-hIL6_binary.csv` | `fitness` | binding_class；0/1 | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/19

论文：A SARS-CoV-2 interaction dataset and VHH sequence corpus for antibody language models（2024）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `tsuruta2024sarscov2_binary.csv` | `fitness` | binding_class；0/1 | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/20

论文：Optimizing antibody affinity and stability by automated VH-VL interface design（2019）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `warszawski2019_d44_Kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/21

论文：Antibody evolution constrains conformational heterogeneity by tailoring protein dynamics（2020）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `zimmerman2020antibody_4420_kd.csv` | `fitness` | negative_log10_KD；-log10(M) | +1（越大越好） | experimental | Gold | supplied paper plus original CSV measurement column | □ 同意 / □ 修改： |

### 初赛-序列数据/22

论文：No supplied paper; ProteinBase auxiliary export（2026）

| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |
|---|---|---|---:|---|---|---|---|
| `proteinbase_all_data_28_01_2026.csv` | `—` | none； | 0（无监督标签） | unlabeled | Auxiliary | supplied paper plus original CSV measurement column；evaluations is structured auxiliary metadata, not a directly supported numeric label | □ 同意 / □ 修改： |

## 五、审核签字区

- 审核人：
- 审核日期：
- 总体结论：□ 全部同意　□ 有修改（请在表中注明）
- 其他备注：

## 六、程序接口

本文件由 `configs/label_registry.csv` 自动渲染。修改正式方向时，应先修改登记表或生成规则，再重新生成本文件，避免文档与代码不一致。

```powershell
python scripts/render_label_direction_review.py `
  --registry configs/label_registry.csv `
  --output docs/curation/MANUAL_LABEL_DIRECTION_REVIEW.md
```
