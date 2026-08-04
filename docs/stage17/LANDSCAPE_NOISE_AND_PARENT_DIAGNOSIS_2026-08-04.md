# 阶段17：Landscape 差异、重复测量噪声与母本代理

## Landscape 有什么不同

| 属性 | landscape1 | landscape2 |
| --- | ---: | ---: |
| 原始记录 | 352,139 | 395,362 |
| 唯一重轻链 | 87,807 | 67,142 |
| 每序列平均重复测量 | 4.01 | 5.89 |
| 标签冲突序列比例 | 83.98% | 93.57% |
| 主要重轻链长度组合 | 3 | 1 |
| validation 同序列均值上限 | 0.6991 | 0.8756 |
| 阶段17最终分来源 Spearman | 0.2747 | 0.6561 |

landscape2 基本是单一 118/113 重轻链长度的局部突变地形，训练和验证共享一致的坐标体系。landscape1 混合 117/108、118/113、119/115 三类主要母本/构型，重复标签噪声更大；同一全局位点编号不一定具有相同结构含义。因此同一位置模型在 landscape2 上容易泛化，在 landscape1 上明显受限。

## 阶段17实验

| 模型 | Spearman | Top-10 enrichment | 判断 |
| --- | ---: | ---: | --- |
| 阶段16正式候选 | 0.460262 | 4.231856 | 基线 |
| 每序列等权均值训练 | 0.446851 | **4.293004** | 头部互补，不单独晋升 |
| sqrt(重复次数)置信训练 | 0.448443 | 4.259267 | 中间噪声折中 |
| 三噪声制度融合 | 0.460876 | 4.259267 | 小幅晋升 |
| 长度母本代理模型 | 0.450795 | 4.269810 | 仅粗代理 |
| **阶段17最终融合** | **0.461437** | **4.257159** | 当前正式严格候选 |

阶段17相对阶段15的 0.437795 累计提高 0.023642，但距离优秀目标仍远。

## 距离 0.9 与第一名

官方页面未能通过当前环境读取公开排行榜，因此未知第一名分数，不能声称与榜首相差某个具体数值。内部严格验证距离 0.9 尚差 0.438563；但 landscape1 的记录级重复标签上限约 0.699，说明在当前记录口径下整体 0.9 很可能并非可达目标。更合理目标是先逼近各 landscape 的噪声上限，并以官方隐藏测试为最终准绳。

## 拿第一的提高方向

1. **P0：真实母本识别。**在 train fold 的 heavy+light ESM 表征上聚类，validation 只分配到 train 中心；不再把长度当母本。
2. **P0：母本残基差分。**输入每个位点 `parent residue → mutant residue`、局部上下文和重轻链位置交互，而不是只输入绝对序列。
3. **P0：Landscape1 专家。**单独优化三类母本，使用组内 listwise/pairwise loss，把 0.275 提到至少 0.4。
4. **P1：抗原/表位条件。**补齐可追溯抗原与表位序列，使用抗体专用 LM + ESM antigen + CDR cross-attention。
5. **P1：噪声模型。**重复实验不简单展开；同时预测均值与观测方差，按不确定性降低冲突标签权重。
6. **P1：独立 test。**冻结方案后只在 v2 test 评估一次，避免 validation 反复调权造成虚高。

## 产物

- `artifacts/stage17/global_family_v2_aggregated_assay_positional_conv/`
- `artifacts/stage17/global_family_v2_sqrt_repeat_assay_positional_conv/`
- `artifacts/stage17/global_family_v2_parent_proxy_positional_conv/`
- `artifacts/stage17/global_family_v2_final_parent_ensemble.csv`
- `artifacts/stage17/global_family_v2_final_parent_ensemble.metrics.json`

代码测试：68 passed。
