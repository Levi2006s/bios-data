# 数据与抗体序列提交清单

## 提交范围

当前阶段只提交常规重链+轻链抗体，不提交 VHH。VHH 的判定规则为轻链为空，原始纳米抗体数据和明确的 VHH 数据集不进入训练与导出。

## 主要文件

| 文件 | 内容 |
|---|---|
| `data/processed/benchmark_team_routed_v6_global_family.csv` | 最终训练、验证、测试路由表 |
| `deliverables/antibody_sequences.csv.gz` | 去重、已评分、非 VHH 重轻链序列 |
| `deliverables/MANIFEST.sha256` | 提交文件 SHA-256 完整性校验 |

## 序列字段

- `sequence_id`：由 `heavy + separator + light` 的 SHA-256 截断得到；
- `rank`：确定性降序名次；
- `score`：Stage 21 固定秩融合分数；
- `heavy`：抗体重链可变区氨基酸序列；
- `light`：抗体轻链可变区氨基酸序列；
- `source_count`：该唯一重轻链对出现的数据来源数量。

输出不包含湿实验成功声明。序列仅用于 benchmark 排名与后续实验优先级。

## 数据治理

原始数据来自赛事提供的公开数据集合。处理流程保留来源追踪，校正终点方向，区分 KD/IC50/EC50/binding/ADCC，去除跨论文镜像重复，并建立精确身份和 family 隔离。最终提交表中训练—验证精确重轻链交集为 0。

大型原始文件和可再生中间表不进入 Git；提交包以 manifest、生成脚本和最终压缩序列表保证可核验性。
