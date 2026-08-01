# 03 - 论文与标签方向人工复核

## 模块简介

本模块逐篇检查原始数据附带的 21 篇论文，并将论文中的实验指标与 83 个 CSV 的实际字段和值域对应起来。最终原则是：**模型训练时统一为“标准化分数越大越好”，但原始标签本身不被偷偷改写。**

IgLM 是序列生成模型，主要学习自然抗体序列并进行片段补全；它没有给出一个通用的亲和力标签方向。因此，IgLM 可以帮助生成或评价“序列像不像抗体”，但不能替代各数据集论文对 KD、IC50、EC50、结合信号等指标的定义。参考：[IgLM 论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC11018345/)。

## 人工确认规则

| 原始指标 | 原始数值如何理解 | 统一方向 |
|---|---|---:|
| KD、Kd | 解离常数越小，结合越强 | -1 |
| `log10(KD)` | 越小代表 KD 越小 | -1 |
| `-log10(KD)` | 越大代表 KD 越小 | +1 |
| IC50、EC50 | 达到半数效果所需浓度越小越好 | -1 |
| binder/non-binder | 1 表示 binder | +1 |
| 实验结合信号 | 经论文确认后，信号越大越好 | +1 |
| 预测的 `log10 KD(nM)` | 只是模型预测弱标签；越小越好 | -1 |

AVIDa-hIL6 论文将显著富集的 VHH-抗原对标为 binder，因此二分类中 1 是更优标签。参考：[AVIDa-hIL6 原论文](https://papers.neurips.cc/paper_files/paper/2023/file/8339dacd9df7ffe9623760f74169dd1e-Paper-Datasets_and_Benchmarks.pdf)。

## 22 个来源组的复核结论

| 组 | 主要指标 | 方向 | 等级 | 备注 |
|---:|---|---:|---|---|
| 1 | `-log10(KD[M])` | +1 | Gold | CSV 含原始 KD 和负对数转换 |
| 2 | ADCC EC50 / `-log10 KD` | -1 / +1 | Gold | 按文件分别登记 |
| 3 | 预测 `log10 KD(nM)` | -1 | Weak | 预测标签，不是湿实验真值 |
| 4 | `log10(KD/IC50)` | **-1** | Silver | 原自动猜测为 +1，已纠正 |
| 5 | KD(M) | -1 | Gold | Tite-Seq/flow |
| 6 | 预测 `log10 KD(nM)` | -1 | Weak | 与来源 3 大量重合 |
| 7 | `-log10(KD[M])` | +1 | Gold | 实验亲和力 |
| 8 | `-log10(KD[M])` | +1 | Gold | Fab/IgG 多种测量 |
| 9 | KD(nM) / binder | -1 / +1 | Gold | CSV 表头写 M，但论文和值域显示为 nM |
| 10 | `-log10(KD[M])` | +1 | Gold | Biacore KD |
| 11 | EC50 / `-log10 SPR KD` | -1 / +1 | Gold | 按文件分别登记 |
| 12 | ANT/OVA 结合信号 | +1 | Silver | 相对信号，不是绝对 KD |
| 13 | `-log10(KD[M])` | +1 | Gold | 流感抗体亲和力景观 |
| 14 | IC50 / `-log10 KD` | -1 / +1 | Gold | 中和与亲和力分开 |
| 15 | `-log10(KD[M])` | +1 | Gold | 实验 KD |
| 16 | KD(nM) | -1 | Gold | IgDesign 湿实验验证 |
| 17 | KD(M) / IC50 | -1 | Gold | 3 个不合理 KD 值被隔离 |
| 18 | binder 0/1 | +1 | Gold | 1=binder |
| 19 | binder 0/1 | +1 | Gold | 1=binder |
| 20 | `-log10(KD[M])` | +1 | Gold | VH-VL 界面设计 |
| 21 | `-log10(KD[M])` | +1 | Gold | 实验 KD |
| 22 | 无直接数值标签 | 0 | Auxiliary | 不进入监督学习 |

AbRank 论文将任务定义为亲和力排序，并强调异质实验标签更适合相对比较。参考：[AbRank 原论文](https://arxiv.org/abs/2506.17857)。CSV 中 `fitness=log_Aff`，例如 815 nM 对应 2.9112，即 `log10(815)`，所以这里必须按“越小越好”处理。

## 输出与接口

- 逐文件登记表：`configs/label_registry.csv`
- 论文证据摘录：`artifacts/curation/paper_label_evidence.json`
- 可复现生成脚本：`scripts/build_label_registry.py`

```powershell
python scripts/build_label_registry.py
```

