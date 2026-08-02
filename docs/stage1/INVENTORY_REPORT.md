# 阶段1：首轮数据清单与结构审计

> 本报告由 `scripts/audit_stage1.py` 生成。字段角色只是启发式候选，尚未完成标签语义人工注册。

## 结论

- 审计记录：86（CSV/TSV 每文件一条，XLSX 每工作表一条）。
- 物理行数合计：4,685,635；扣除已确认的完整重复文件后约 4,655,302 行。
- 前导说明行/错位表头：1 个文件。
- CSV/TSV 列宽异常：0 个文件。
- 未自动识别候选序列字段：1 条记录；未自动识别标签字段：1 条记录。
- 所有源文件仅被读取；没有解压 ZIP，也没有向 `data/` 写入。

## 已确认异常

- `初赛-序列数据/3/li2023machine_scFv-SARS-CoV-2_affinity2.csv`：真实表头在第 7 行。
- 完整重复文件（SHA-256 相同）：`初赛-纳米抗体数据/ANDD(1).xlsx`、`初赛-纳米抗体数据/ANDD.xlsx`。

## 最大数据表

| 行数 | 路径 |
|---:|---|
| 1,903,921 | `初赛-序列数据/3/li2023machine_scFv-SARS-CoV-2_affinity2.csv` |
| 1,259,700 | `初赛-序列数据/3/li2023machine_scFv-SARS-CoV-2_affinity1.csv` |
| 573,891 | `初赛-序列数据/18/tsuruta2024avida-hIL6_binary.csv` |
| 352,139 | `初赛-序列数据/6/engelhart2022dataset_scFv-SARS-CoV-2_affinity.csv` |
| 342,356 | `初赛-序列数据/4/AbRank_dataset.csv` |
| 77,003 | `初赛-序列数据/19/tsuruta2024sarscov2_binary.csv` |
| 32,767 | `初赛-序列数据/13/phillips2021binding_cr9114_h3_kd.csv` |
| 32,392 | `初赛-序列数据/13/phillips2021binding_cr9114_h1_kd.csv` |
| 30,333 | `初赛-纳米抗体数据/ANDD(1).xlsx` |
| 30,333 | `初赛-纳米抗体数据/ANDD.xlsx` |

## 当前边界

1. `label_candidates` 仅按列名推断，不能替代对论文、单位、方向、截断和 assay 的人工登记。
2. 序列合法性与缺失统计只覆盖每个表前若干样本行，详见 inventory 的 `sampled_rows`。
3. XLSX 行数取工作表 dimension；正式标准化前需逐表复核隐藏行、公式和合并单元格。
4. 结构 ZIP 与 INDI2 ZIP 本轮仍只保留为归档，不进行解压。

## 下一验收门

逐文件建立标签注册表，至少确认 `study_id / assay_type / unit / direction / label_column / quality_tier / comparable_group / censoring`，未确认文件默认隔离。
