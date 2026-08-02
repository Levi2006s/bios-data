# 人工标签方向审核表（医学生易读版）

> 这份表同时回答：数字本身怎么读、开发时偏好什么方向，以及它能不能作为 KD 亲和力标签。

## 一、先理解四个常见概念

### 1. KD：结合有多牢

KD 可以简单理解成抗体和抗原“分开有多容易”。**KD 越小，通常结合越牢，亲和力越强。**例如 1 nM 通常优于 100 nM。

### 2. IC50 和 EC50：需要多少浓度才能产生一半效果

如果达到相同效果只需要更低浓度，一般说明效力更强。因此 **IC50、EC50 通常越小越好**。但它们描述的是功能效果，不完全等同于 KD。

### 3. 为什么有些 KD 分数反而越大越好

有些作者会计算 `-log10(KD)`。因为前面加了负号，方向发生翻转：**这种分数越大，代表原始 KD 越小，也就是越好。**

### 4. 实验结果可信，不等于能代表 KD

例如 ADCC EC50 可以是真实而重要的功能实验，但它还受 Fc 受体、糖基化和效应细胞影响，所以不能直接当成 KD。AlphaSeq 则是实验衍生、模型校准的亲和力估计，也不能简单写成纯计算伪标签。

## 二、总体结论

- 共审核 83 个 CSV 文件；
- 47 个文件是“数值越大越好”；
- 34 个文件是“数值越小越好”；
- 2 个文件没有可直接比较好坏的标签。

## 三、最需要注意的六组数据

- **来源 4（AbRank）**：混有 KD、IC50、escape 和排序值，没有统一方向；必须先按 measurement type 拆分。
- **来源 9**：连续 KD 文件的列名标成 M，但论文和数值大小更符合 nM；方向是越小越好。
- **来源 3、6**：AlphaSeq 是实验衍生、模型校准的估计，亲和力等级 B/C，不能让其大样本压过 SPR。
- **来源 12**：目标抗原信号与 OVA 风险必须分开；OVA 信号越大代表非特异结合风险越高，开发时越小越好。
- **来源 17**：有 3 条 KD 为零或明显超出合理范围，已经隔离。
- **来源 22**：没有可直接使用的数值标签，不进入监督训练。

## 四、逐文件审核

### 初赛-序列数据/1

对应论文：Assessment and incorporation of in vitro correlates to pharmacokinetic outcomes in antibody developability workflows（2024）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `jain2024assessment_Hen_Lys_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `jain2024assessment_mouse_Ly_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/2

对应论文：Unlocking de novo antibody design with generative artificial intelligence（2023）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `shanehsazzadeh2023unlocking_adcc_ec50.csv` | ADCC EC50 | 越小=半最大细胞毒效应所需浓度更低 | 越小通常越好 | 原终点 A/B；亲和力监督 D；任务：adcc_function | 该指标与靶细胞密度等因素有关，不能直接翻译亲和力。 |
| `shanehsazzadeh2023unlocking_kd_hher2_fab.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `shanehsazzadeh2023unlocking_kd_hher2_mab.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `shanehsazzadeh2023unlocking_zerokd_trastuzumab.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/3

对应论文：Machine learning optimization of candidate antibody yields highly diverse sub-nanomolar affinity antibody libraries（2023）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `li2023machine_scFv-SARS-CoV-2_affinity1.csv` | AlphaSeq 校准的log10(KD[nM])估计 | 越小=估计 KD 更低 | 越小通常越好 | 原终点 B；亲和力监督 B/C；任务：affinity_kd | 不是纯计算伪标签 |
| `li2023machine_scFv-SARS-CoV-2_affinity2.csv` | AlphaSeq 校准的log10(KD[nM])估计 | 越小=估计 KD 更低 | 越小通常越好 | 原终点 B；亲和力监督 B/C；任务：affinity_kd | 不是纯计算伪标签 |

### 初赛-序列数据/4

对应论文：AbRank: A Benchmark Dataset and Metric-Learning Framework for Antibody-Antigen Affinity Ranking（2025）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `AbRank_dataset.csv` | 混合 KD、IC50、escape 及排序值 | 无全局统一方向 | 依measurement_type 决定 | 原终点 B/C；亲和力监督 C/D；任务：mixed_endpoint_split_required | 需拆分终点 |

### 初赛-序列数据/5

对应论文：Measuring the sequence-affinity landscape of antibodies with massively parallel titration curves（2017）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `adams2017measuring_4420-fluorescein_kd-flow.csv` | 高通量滴定拟合 KD | 越小=亲和力更强 | 越小通常越好 | 原终点 A/B；亲和力监督 B；任务：affinity_kd | 记录拟合质量、截断值和表达校正（ai建议） |
| `adams2017measuring_4420-fluorescein_kd-titeseq.csv` | 高通量滴定拟合 KD | 越小=亲和力更强 | 越小通常越好 | 原终点 A/B；亲和力监督 B；任务：affinity_kd | 记录拟合质量、截断值和表达校正（ai建议） |

### 初赛-序列数据/6

对应论文：A dataset comprised of binding interactions for 104,972 antibodies against a SARS-CoV-2 peptide（2022）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `engelhart2022dataset_scFv-SARS-CoV-2_affinity.csv` | AlphaSeq 校准的log10(KD[nM])估计 | 越小=估计 KD 更低 | 越小通常越好 | 原终点 B；亲和力监督 B/C；任务：affinity_kd | 不是纯计算伪标签；大样本，不能压过高质量SPR |

### 初赛-序列数据/7

对应论文：Efficient evolution of human antibodies from general protein language models（2023）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `hie2023efficient_CoV2Beta_C143_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_CoV2Beta_REGN10987_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_CoV2_S309_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_CoV2omicron_REGN10987_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_MEDIUCA_H1Solomon_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_MEDIUCA_H4Hubei_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_MEDI_H4Hubei_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_MEDI_H7HK16_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `hie2023efficient_ebola_mab114_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/8

对应论文：Toward enhancement of antibody thermostability and affinity by computational design in the absence of antigen（2023）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `hutchinson2023enhancement_multikd_fab.csv` | pKD / -log10(KD) (Fab) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_multikd_igg.csv` | pKD / -log10(KD) (IgG) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_singlekd_fab.csv` | pKD / -log10(KD) (Fab) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_singlekd_igg.csv` | pKD / -log10(KD) (IgG) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_top200kd_fab.csv` | pKD / -log10(KD) (Fab) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_top200kd_igg.csv` | pKD / -log10(KD) (IgG) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_top27kd_fab.csv` | pKD / -log10(KD) (Fab) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |
| `hutchinson2023enhancement_top27kd_igg.csv` | pKD / -log10(KD) (IgG) | 越大=亲和力/表观亲合力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 B；任务：affinity_kd | Fab 与 IgG 分开建模；IgG 可能含双价 avidity |

### 初赛-序列数据/9

对应论文：Retrospective SARS-CoV-2 human antibody development trajectories are largely sparse and permissive（2024）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `kirby2024retrospective_ab-SARSCoV2_binary_kd.csv` | bind/no-bind | 1=达到阳性阈值 | 1 通常优于0 | 原终点 A/B；亲和力监督 D；任务：binding_classification | 非定量分析 |
| `kirby2024retrospective_ab-SARSCoV2_kd.csv` | 原始 KD（单位待复核） | 越小=亲和力更强 | 越小通常越好 | 原终点 B；亲和力监督 B/C；任务：affinity_kd | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 |

### 初赛-序列数据/10

对应论文：Mutational landscape of antibody variable domains reveals a switch modulating interdomain dynamics and antigen binding（2017）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `koenig2017mutational_kd_g6.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/11

对应论文：High-Throughput Machine Learning-Aided Antibody Discovery for Cell Surface Antigens（2025）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `kothiwal2025htp_DCC_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_DCC_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_DKK_1.00_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_DKK_1.00_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_IL23R_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_IL23R_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_LOX1_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_LOX1_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_PDL1_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_PDL1_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_PDL2_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_PDL2_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_ROBO1_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_ROBO1_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_ROBO2N_hROBO2N_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_ROBO2N_hROBO2N_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_Syncytin2_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_Syncytin2_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |
| `kothiwal2025htp_TIGIT_ec50.csv` | 结合/效应 EC50 | 越小=半最大反应所需浓度更低 | 通常越小越好 | 原终点 A/B；亲和力监督 B/C；任务：binding_ec50 | 独立 EC50 任务；不得等同 KD |
| `kothiwal2025htp_TIGIT_spr.csv` | SPR pKD / -log10(KD[M]) | 越大=KD 更低 | 越大通常越好 | 原终点 A；亲和力监督 A；任务：affinity_kd | 保留 kon/koff 与拟合模型；勿与 EC50 直接合并 |

### 初赛-序列数据/12

对应论文：Co-optimization of therapeutic antibody affinity and specificity using machine learning（2022）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `makowksi2022cooptimization_iso_ant.csv` | 目标抗原相对结合信号 | 越大=检测到的目标结合更强 | 通常越大越好 | 原终点 B；亲和力监督 C；任务：relative_target_binding | 作为相对信号任务；控制表达量与背景 |
| `makowski2022cooptimization_igg_ant.csv` | 目标抗原相对结合信号 | 越大=检测到的目标结合更强 | 通常越大越好 | 原终点 B；亲和力监督 C；任务：relative_target_binding | 作为相对信号任务；控制表达量与背景 |
| `makowski2022cooptimization_igg_ova.csv` | OVA 非特异性/多反应性结合信号 | 越大=非特异结合更强 | 越小通常越好 | 原终点 B；亲和力监督 D；任务：developability_ova_risk | 方向改为开发价值越小越好；作为风险约束 |
| `makowski2022cooptimization_iso_ova.csv` | OVA 非特异性/多反应性结合信号 | 越大=非特异结合更强 | 越小通常越好 | 原终点 B；亲和力监督 D；任务：developability_ova_risk | 方向改为开发价值越小越好；作为风险约束 |

### 初赛-序列数据/13

对应论文：Binding affinity landscapes constrain the evolution of broadly neutralizing anti-influenza antibodies（2021）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `phillips2021binding_cr6261_h1_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `phillips2021binding_cr6261_h9_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `phillips2021binding_cr9114_h1_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `phillips2021binding_cr9114_h3_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/14

对应论文：Ab-CoV: binding affinity and neutralization profiles of coronavirus-related antibodies（2022）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `rawat2022abcov_ic50.csv` | 抑制/中和 IC50 | 越小=体外效力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 C；任务：neutralization_ic50 | 独立功能终点；不得并入 KD 回归 |
| `rawat2022abcov_kd.csv` | 文献汇总 pKD / -log10(KD) | 越大=记录的 KD 更低 | 通常越大越好 | 原终点 B/C；亲和力监督 B/C；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/15

对应论文：Automated optimisation of solubility and conformational stability of antibodies and proteins（2023）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `rosace2023automated_kd_adalimumab.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |
| `rosace2023automated_kd_golimumab.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/16

对应论文：IgDesign: in vitro validated antibody design using inverse folding（2024）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `shanehsazzadeh2024igdesign_Afasevikumab-IL17A_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |
| `shanehsazzadeh2024igdesign_Bimagrumab-ACVR2B_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |
| `shanehsazzadeh2024igdesign_Eculizumab-C5_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |
| `shanehsazzadeh2024igdesign_Osocimab-FXI_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |
| `shanehsazzadeh2024igdesign_Spesolimab-IL36R_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |
| `shanehsazzadeh2024igdesign_Tezepelumab-TSLP_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |
| `shanehsazzadeh2024igdesign_Utomilumab-TNFRSF9_kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 统一换算为 M 后计算 pKD；保留分子格式 |

### 初赛-序列数据/17

对应论文：Unsupervised evolution of protein and antibody complexes with a structure-informed language model（2024）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `shanker2024unsupervised_Ly1404-BQ.1.1_IC50.csv` | 抑制/中和 IC50 | 越小=体外效力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 C；任务：neutralization_ic50 | 独立功能终点；不得并入 KD 回归 |
| `shanker2024unsupervised_Ly1404-BQ.1.1_Kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 复核并隔离已知异常 KD；保留原始曲线/重复信息 |
| `shanker2024unsupervised_Ly1404_Wuhan_IC50.csv` | 抑制/中和 IC50 | 越小=体外效力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 C；任务：neutralization_ic50 | 独立功能终点；不得并入 KD 回归 |
| `shanker2024unsupervised_SA58-BA.1_IC50.csv` | 抑制/中和 IC50 | 越小=体外效力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 C；任务：neutralization_ic50 | 独立功能终点；不得并入 KD 回归 |
| `shanker2024unsupervised_SA58-BQ.1.1_IC50.csv` | 抑制/中和 IC50 | 越小=体外效力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 C；任务：neutralization_ic50 | 独立功能终点；不得并入 KD 回归 |
| `shanker2024unsupervised_SA58-BQ.1.1_Kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 复核并隔离已知异常 KD；保留原始曲线/重复信息 |
| `shanker2024unsupervised_SA58-XBB.1.5_Kd.csv` | 原始 KD | 越小=亲和力更强 | 通常越小越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 复核并隔离已知异常 KD；保留原始曲线/重复信息 |

### 初赛-序列数据/18

对应论文：AVIDa-hIL6: a large-scale VHH interaction dataset（2023）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `tsuruta2024avida-hIL6_binary.csv` | bind/no-bind | 1=达到阳性阈值 | 1 通常优于0 | 原终点 A/B；亲和力监督 D；任务：binding_classification | 非定量 |

### 初赛-序列数据/19

对应论文：A SARS-CoV-2 interaction dataset and VHH sequence corpus for antibody language models（2024）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `tsuruta2024sarscov2_binary.csv` | bind/no-bind | 1=达到阳性阈值 | 1 通常优于0 | 原终点 A/B；亲和力监督 D；任务：binding_classification | 非定量 |

### 初赛-序列数据/20

对应论文：Optimizing antibody affinity and stability by automated VH-VL interface design（2019）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `warszawski2019_d44_Kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/21

对应论文：Antibody evolution constrains conformational heterogeneity by tailoring protein dynamics（2020）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `zimmerman2020antibody_4420_kd.csv` | pKD / -log10(KD) | 越大=亲和力更强 | 通常越大越好 | 原终点 A/B；亲和力监督 A/B；任务：affinity_kd | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 |

### 初赛-序列数据/22

对应论文：No supplied paper; ProteinBase auxiliary export（2026）

| 文件 | 这个数字表示什么 | 原始数值怎么读 | 开发时偏好 | 可信度与任务 | 处理意见 |
|---|---|---|---|---|---|
| `proteinbase_all_data_28_01_2026.csv` | 无监督序列/辅助数据 | 无方向 | 不适用 | 原终点 NA；亲和力监督 NA；任务：unsupervised | 仅用于预训练、去重或外部表征；不得进入监督评估 |

## 五、审核完成后怎么反馈

如果你认为某一行有问题，只需要告诉我：来源编号、文件名、你认为正确的方向，以及依据。例如：

> 来源 4，AbRank_dataset.csv，我认为某一种 measurement type 应按越小越好处理，依据是……

- 审核人：
- 审核日期：
- 总体结论：□ 同意　□ 需要修改

## 六、重新生成本文档

```powershell
python scripts/render_medical_label_review.py `
  --registry configs/label_registry.csv `
  --output docs/curation/MANUAL_LABEL_DIRECTION_REVIEW_MEDICAL.md
```
