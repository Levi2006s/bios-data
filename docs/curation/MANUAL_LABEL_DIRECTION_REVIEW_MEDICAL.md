# 人工标签方向审核表（医学生易读版）

> 这份表回答一个核心问题：每个数据文件里的数字，到底是越大越好，还是越小越好？

## 一、先理解四个常见概念

### 1. KD：结合有多牢

KD 可以简单理解成抗体和抗原“分开有多容易”。**KD 越小，通常结合越牢，亲和力越强。**例如 1 nM 通常优于 100 nM。

### 2. IC50 和 EC50：需要多少浓度才能产生一半效果

如果达到相同效果只需要更低浓度，一般说明效力更强。因此 **IC50、EC50 通常越小越好**。但它们描述的是功能效果，不完全等同于 KD。

### 3. 为什么有些 KD 分数反而越大越好

有些作者会计算 `-log10(KD)`。因为前面加了负号，方向发生翻转：**这种分数越大，代表原始 KD 越小，也就是越好。**

### 4. 实验标签和预测标签不能等同

实验标签来自 SPR、细胞实验、酵母展示或中和实验；预测标签是另一个模型算出来的结果。预测标签可以帮助扩大数据量，但不能当成真正的实验结论。

## 二、总体结论

- 共审核 83 个 CSV 文件；
- 49 个文件是“数值越大越好”；
- 33 个文件是“数值越小越好”；
- 1 个文件没有可直接比较好坏的标签。

## 三、最需要注意的六组数据

- **来源 4（AbRank）**：虽然字段叫 `fitness`，实际保存的是 KD/IC50 的对数，仍然应该越小越好。
- **来源 9**：连续 KD 文件的列名标成 M，但论文和数值大小更符合 nM；方向是越小越好。
- **来源 3、6**：标签是模型预测结果，不是湿实验结果，列为弱标签。
- **来源 12**：标签是相对结合信号，不是 KD，只适合同一实验内比较。
- **来源 17**：有 3 条 KD 为零或明显超出合理范围，已经隔离。
- **来源 22**：没有可直接使用的数值标签，不进入监督训练。

## 四、逐文件审核

### 初赛-序列数据/1

对应论文：Assessment and incorporation of in vitro correlates to pharmacokinetic outcomes in antibody developability workflows（2024）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `jain2024assessment_Hen_Lys_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `jain2024assessment_mouse_Ly_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/2

对应论文：Unlocking de novo antibody design with generative artificial intelligence（2023）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `shanehsazzadeh2023unlocking_adcc_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2023unlocking_kd_hher2_fab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2023unlocking_kd_hher2_mab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2023unlocking_zerokd_trastuzumab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/3

对应论文：Machine learning optimization of candidate antibody yields highly diverse sub-nanomolar affinity antibody libraries（2023）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `li2023machine_scFv-SARS-CoV-2_affinity1.csv` | 模型预测的 KD 对数值（不是实验结果） | 数值越小越好 | 它估计的是 KD，因此越小越好；但这是模型预测，只能当辅助信息。 | 弱标签：来自模型预测，不等同于实验真值 | □ 同意　□ 修改： |
| `li2023machine_scFv-SARS-CoV-2_affinity2.csv` | 模型预测的 KD 对数值（不是实验结果） | 数值越小越好 | 它估计的是 KD，因此越小越好；但这是模型预测，只能当辅助信息。 | 弱标签：来自模型预测，不等同于实验真值 | □ 同意　□ 修改： |

### 初赛-序列数据/4

对应论文：AbRank: A Benchmark Dataset and Metric-Learning Framework for Antibody-Antigen Affinity Ranking（2025）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `AbRank_dataset.csv` | KD 或 IC50 取对数后的数值 | 数值越小越好 | 这里只取了对数，没有加负号，因此仍然是越小越好。不同实验类型不能直接混比。 | 中等可信：实验来源明确，但指标或单位不完全统一 | □ 同意　□ 修改： |

### 初赛-序列数据/5

对应论文：Measuring the sequence-affinity landscape of antibodies with massively parallel titration curves（2017）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `adams2017measuring_4420-fluorescein_kd-flow.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `adams2017measuring_4420-fluorescein_kd-titeseq.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/6

对应论文：A dataset comprised of binding interactions for 104,972 antibodies against a SARS-CoV-2 peptide（2022）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `engelhart2022dataset_scFv-SARS-CoV-2_affinity.csv` | 模型预测的 KD 对数值（不是实验结果） | 数值越小越好 | 它估计的是 KD，因此越小越好；但这是模型预测，只能当辅助信息。 | 弱标签：来自模型预测，不等同于实验真值 | □ 同意　□ 修改： |

### 初赛-序列数据/7

对应论文：Efficient evolution of human antibodies from general protein language models（2023）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `hie2023efficient_CoV2Beta_C143_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_CoV2Beta_REGN10987_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_CoV2_S309_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_CoV2omicron_REGN10987_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_MEDIUCA_H1Solomon_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_MEDIUCA_H4Hubei_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_MEDI_H4Hubei_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_MEDI_H7HK16_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hie2023efficient_ebola_mab114_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/8

对应论文：Toward enhancement of antibody thermostability and affinity by computational design in the absence of antigen（2023）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `hutchinson2023enhancement_multikd_fab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_multikd_igg.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_singlekd_fab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_singlekd_igg.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_top200kd_fab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_top200kd_igg.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_top27kd_fab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `hutchinson2023enhancement_top27kd_igg.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/9

对应论文：Retrospective SARS-CoV-2 human antibody development trajectories are largely sparse and permissive（2024）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `kirby2024retrospective_ab-SARSCoV2_binary_kd.csv` | 是否能够与抗原结合（0/1） | 1 更好：1=能结合，0=不能结合 | 数据集已经把实验结果整理成是否结合，1 表示结合。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kirby2024retrospective_ab-SARSCoV2_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/10

对应论文：Mutational landscape of antibody variable domains reveals a switch modulating interdomain dynamics and antigen binding（2017）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `koenig2017mutational_kd_g6.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/11

对应论文：High-Throughput Machine Learning-Aided Antibody Discovery for Cell Surface Antigens（2025）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `kothiwal2025htp_DCC_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_DCC_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_DKK_1.00_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_DKK_1.00_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_IL23R_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_IL23R_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_LOX1_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_LOX1_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_PDL1_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_PDL1_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_PDL2_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_PDL2_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_ROBO1_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_ROBO1_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_ROBO2N_hROBO2N_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_ROBO2N_hROBO2N_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_Syncytin2_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_Syncytin2_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_TIGIT_ec50.csv` | 达到一半效果所需浓度（EC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `kothiwal2025htp_TIGIT_spr.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/12

对应论文：Co-optimization of therapeutic antibody affinity and specificity using machine learning（2022）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `makowksi2022cooptimization_iso_ant.csv` | 实验检测到的相对结合信号 | 数值越大越好 | 在该论文的实验定义中，信号越强代表检测到的结合越明显，但它不是绝对亲和力。 | 中等可信：实验来源明确，但指标或单位不完全统一 | □ 同意　□ 修改： |
| `makowski2022cooptimization_igg_ant.csv` | 实验检测到的相对结合信号 | 数值越大越好 | 在该论文的实验定义中，信号越强代表检测到的结合越明显，但它不是绝对亲和力。 | 中等可信：实验来源明确，但指标或单位不完全统一 | □ 同意　□ 修改： |
| `makowski2022cooptimization_igg_ova.csv` | 实验检测到的相对结合信号 | 数值越大越好 | 在该论文的实验定义中，信号越强代表检测到的结合越明显，但它不是绝对亲和力。 | 中等可信：实验来源明确，但指标或单位不完全统一 | □ 同意　□ 修改： |
| `makowski2022cooptimization_iso_ova.csv` | 实验检测到的相对结合信号 | 数值越大越好 | 在该论文的实验定义中，信号越强代表检测到的结合越明显，但它不是绝对亲和力。 | 中等可信：实验来源明确，但指标或单位不完全统一 | □ 同意　□ 修改： |

### 初赛-序列数据/13

对应论文：Binding affinity landscapes constrain the evolution of broadly neutralizing anti-influenza antibodies（2021）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `phillips2021binding_cr6261_h1_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `phillips2021binding_cr6261_h9_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `phillips2021binding_cr9114_h1_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `phillips2021binding_cr9114_h3_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/14

对应论文：Ab-CoV: binding affinity and neutralization profiles of coronavirus-related antibodies（2022）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `rawat2022abcov_ic50.csv` | 抑制或中和一半目标所需浓度（IC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `rawat2022abcov_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/15

对应论文：Automated optimisation of solubility and conformational stability of antibodies and proteins（2023）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `rosace2023automated_kd_adalimumab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `rosace2023automated_kd_golimumab.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/16

对应论文：IgDesign: in vitro validated antibody design using inverse folding（2024）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `shanehsazzadeh2024igdesign_Afasevikumab-IL17A_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2024igdesign_Bimagrumab-ACVR2B_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2024igdesign_Eculizumab-C5_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2024igdesign_Osocimab-FXI_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2024igdesign_Spesolimab-IL36R_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2024igdesign_Tezepelumab-TSLP_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanehsazzadeh2024igdesign_Utomilumab-TNFRSF9_kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/17

对应论文：Unsupervised evolution of protein and antibody complexes with a structure-informed language model（2024）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `shanker2024unsupervised_Ly1404-BQ.1.1_IC50.csv` | 抑制或中和一半目标所需浓度（IC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanker2024unsupervised_Ly1404-BQ.1.1_Kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanker2024unsupervised_Ly1404_Wuhan_IC50.csv` | 抑制或中和一半目标所需浓度（IC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanker2024unsupervised_SA58-BA.1_IC50.csv` | 抑制或中和一半目标所需浓度（IC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanker2024unsupervised_SA58-BQ.1.1_IC50.csv` | 抑制或中和一半目标所需浓度（IC50） | 数值越小越好 | 达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanker2024unsupervised_SA58-BQ.1.1_Kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |
| `shanker2024unsupervised_SA58-XBB.1.5_Kd.csv` | 抗体与抗原分开的难易程度（KD） | 数值越小越好 | KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/18

对应论文：AVIDa-hIL6: a large-scale VHH interaction dataset（2023）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `tsuruta2024avida-hIL6_binary.csv` | 是否能够与抗原结合（0/1） | 1 更好：1=能结合，0=不能结合 | 数据集已经把实验结果整理成是否结合，1 表示结合。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/19

对应论文：A SARS-CoV-2 interaction dataset and VHH sequence corpus for antibody language models（2024）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `tsuruta2024sarscov2_binary.csv` | 是否能够与抗原结合（0/1） | 1 更好：1=能结合，0=不能结合 | 数据集已经把实验结果整理成是否结合，1 表示结合。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/20

对应论文：Optimizing antibody affinity and stability by automated VH-VL interface design（2019）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `warszawski2019_d44_Kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/21

对应论文：Antibody evolution constrains conformational heterogeneity by tailoring protein dynamics（2020）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `zimmerman2020antibody_4420_kd.csv` | 把 KD 取负对数后的亲和力分数 | 数值越大越好 | 原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。 | 高可信：主要来自明确的实验测量 | □ 同意　□ 修改： |

### 初赛-序列数据/22

对应论文：No supplied paper; ProteinBase auxiliary export（2026）

| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |
|---|---|---|---|---|---|
| `proteinbase_all_data_28_01_2026.csv` | 没有可直接使用的实验标签 | 不比较好坏 | 没有监督标签，只能作为辅助序列数据。 | 辅助数据：没有可直接训练的标签 | □ 同意　□ 修改： |

## 五、审核完成后怎么反馈

如果你认为某一行有问题，只需要告诉我：来源编号、文件名、你认为正确的方向，以及依据。例如：

> 来源 4，AbRank_dataset.csv，我认为应为越小越好，因为 fitness 是 log10(KD)。

- 审核人：
- 审核日期：
- 总体结论：□ 同意　□ 需要修改

## 六、重新生成本文档

```powershell
python scripts/render_medical_label_review.py `
  --registry configs/label_registry.csv `
  --output docs/curation/MANUAL_LABEL_DIRECTION_REVIEW_MEDICAL.md
```
