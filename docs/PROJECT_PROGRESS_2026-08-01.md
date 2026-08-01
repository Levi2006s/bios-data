# Bio-OS 抗体设计项目阶段进度

更新日期：2026-08-01

## 1. 当前结论

项目已经完成正式建模之前的数据基础工程，包括原始数据审计、标签方向审核、序列质量检查、重复与泄漏分析、安全的数据划分，以及 ANARCII 编号输入准备。目前尚未开始大型模型训练。

原始数据共包含 83 个 CSV 文件、4,604,269 条记录，大小约 2.25 GiB。清洗后约有 2,009,775 条记录可作为监督学习数据。

## 2. 已完成模块与接口

### 模块 A：原始数据审计

**模块简介**

逐个扫描 CSV 文件，统计文件规模、字段、标签缺失情况，以及重链、轻链、抗原和 CDRH3 序列是否合法。该模块只读取原始数据，不会修改原文件。

**主要接口**

```bash
python -m bioos_benchmark.audit --input <原始数据目录> --output data/processed/audit.csv
```

**主要输出**

- `data/processed/audit.csv`：每个文件的详细统计。
- `data/processed/audit.summary.json`：全部数据的汇总统计。
- `docs/DATA_AUDIT_REPORT_2026-08-01.md`：适合人工阅读的审计报告。

### 模块 B：标签含义与方向统一

**模块简介**

不同论文中的 KD、IC50、EC50、结合信号和分类标签不能直接混合。本模块记录每个文件的标签含义、单位、数值方向、证据来源和可信等级，并把模型优化方向统一为“数值越大代表候选越好”。

**主要接口**

```bash
python scripts/build_label_registry.py
```

**主要输出**

- `configs/label_registry.csv`：程序可直接读取的标签注册表。
- `configs/direction_overrides.csv`：标签方向修正规则。
- `docs/curation/MANUAL_LABEL_DIRECTION_REVIEW.md`：技术审核版。
- `docs/curation/MANUAL_LABEL_DIRECTION_REVIEW_MEDICAL.md`：医学生易读版。

标签审核已经覆盖全部 83 个文件：74 个 Gold、5 个 Silver、3 个 Weak、1 个 Auxiliary。

### 模块 C：标准化清洗

**模块简介**

递归发现数据文件，统一字段，检查氨基酸序列，过滤无效或超范围标签，并根据标签注册表转换标签方向，得到后续算法能够统一读取的数据。

**主要接口**

```bash
python -m bioos_benchmark.prepare \
  --input <原始数据目录> \
  --label-registry configs/label_registry.csv \
  --output <标准化数据文件>
```

**主要输出字段**

- 抗体重链、轻链和抗原序列。
- 原始标签及统一方向后的标签。
- 数据来源、质量等级和异常原因。

### 模块 D：重复数据与泄漏分析

**模块简介**

识别完全相同的抗体、跨来源重复记录和相似抗体家族，防止同一个或高度相似的抗体同时进入训练集与测试集，从而造成虚高成绩。

**主要接口**

```bash
bioos-curate \
  --input <原始数据目录> \
  --label-registry configs/label_registry.csv \
  --output-dir data/processed/curation
```

也可使用：

```bash
python -m bioos_benchmark.curation \
  --input <原始数据目录> \
  --label-registry configs/label_registry.csv \
  --output-dir data/processed/curation
```

**主要结果**

- 发现约 277,515 个不重复的完整抗体。
- 约 1,732,260 条记录属于完全相同抗体的重复出现。
- 约 438,306 条记录与其他数据组存在完全相同的抗体。
- 第 6 组的 352,139 条有标签数据与第 3 组重复。

### 模块 E：安全数据划分

**模块简介**

为每条数据生成多套训练集、验证集和测试集标识。评估时可以按抗体家族、抗原、论文来源或时间隔离，检查模型面对真正新样本时的能力。

**主要接口**

```bash
bioos-apply-splits \
  --input <标准化数据文件> \
  --manifest data/processed/curation/split_group_manifest.csv \
  --output <带划分字段的数据文件>
```

**主要输出**

- `data/processed/curation/split_group_manifest.csv`：划分规则清单。
- `data/processed/curation/curated_sample_with_splits.csv`：带划分字段的示例数据。
- `docs/curation/07_SPLIT_STRATEGIES.md`：划分方法说明。

建议正式报告至少展示“抗体家族隔离”“抗原隔离”和“论文来源隔离”三组结果。

### 模块 F：ANARCII 编号输入准备

**模块简介**

从数据中提取并去重抗体重链和轻链，生成 FASTA 文件，供云端 ANARCII 进行 IMGT 编号和 CDR 区域定位。本阶段只准备输入，没有在本机执行计算量较大的编号程序。

**主要接口**

```text
输入：data/processed/curation/imgt_numbering_input.fasta
输出：由云端 ANARCII 生成的编号结果
```

当前测试输入包含 2,110 条去重后的重链或轻链序列。

### 模块 G：自动验证

**模块简介**

使用自动测试检查标签转换、偏好对、数学排序、评估和数据处理中的关键逻辑，减少修改代码时引入错误的风险。

**主要接口**

```bash
python -m pytest
```

当前已有 21 项测试通过。

## 3. 尚未完成的工作

数学路线下一阶段：

1. 从同一抗原下的抗体构建“A 优于 B”的偏好对。
2. 建立可解释的 Bradley-Terry、逻辑回归或成对排序基线。
3. 计算 Spearman 相关系数、Top-K 富集率、宏平均和置信区间。
4. 设置负对照，并检查模型是否利用了重复序列或数据来源捷径。

计算机路线下一阶段：

1. 在云端运行 ANARCII。
2. 接入 IgLM 或其他抗体预训练模型。
3. 提取抗体与抗原表示并训练深度模型。
4. 输出统一格式的预测结果，交由数学评估模块比较。

## 4. 公开仓库中的数据说明

公开仓库保存源代码、配置、测试和说明文档。原始比赛数据、大体积处理结果、本机虚拟环境、缓存、临时渲染文件及模型产物不直接提交。使用者需自行取得原始数据，然后按照 README 中的命令重新生成处理结果。

这样既避免公开传播可能受限制的数据，也能保证整个处理流程可以复现。
