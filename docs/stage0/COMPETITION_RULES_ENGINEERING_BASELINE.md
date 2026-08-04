# 阶段0：赛题规则与工程基线

> 审计时间：2026-07-26（Asia/Shanghai）  
> 项目根目录：`/root/BioOS`  
> 范围：规则、数据目录与工程环境审计；未训练模型，未生成或优化任何序列。  
> 主要证据：赛事官方全文、[DataCastle 官方页面（id=1198）](https://challenge.datacastle.cn/v3/cmptDetail.html?id=1198)、`idea.md`、`data/README.md`、文件系统元数据、ZIP 中央目录、系统与 Python 环境命令输出。  
> 官方规则补充核验日期：2026-07-26。

## 技术摘要

阶段0工程基线已经具备。`data` 中共有 **122 个文件、30.405 GiB**，外层类型为 83 CSV、21 PDF、13 ZIP、2 XLSX、1 TSV、1 MD 和 1 `.gitattributes`。13 个 ZIP 仅检查了中央目录，没有解压；结构 ZIP 含 31,550 个 PDB 条目，12 个 INDI2 分片的目录索引显示 Parquet、CSV/TSV、JSON、文本及压缩数据。当前环境是 Python 3.11.7、PyTorch 2.2.2（CUDA 12.1 构建）。二次核验确认宿主环境有 **1 张 NVIDIA GeForce RTX 4090**，`nvidia-smi` 报告 49,140 MiB 显存、驱动 550.78、CUDA 12.4；沙箱外 `torch.cuda.is_available() == True`。首次审计进程因受限沙箱未映射 `/dev/nvidia*` 而误报 GPU 0，不能据此推断宿主机没有 GPU。

赛事官方全文现已确认：初赛使用标准数据集预测抗原—抗体亲和力，对候选抗体排序，并以预测排序和真实排序的 Spearman correlation 评价；周期为 2026-04-01 至 2026-08-07，前 20 支队伍晋级第二阶段。**初赛不是直接生成候选抗体的任务**。因此当前主线是抗原条件下的亲和力排序模型，而不是从零训练生成式基础模型。第二阶段只预留 Binding、Expression、Aggregation、Novelty 和 Portfolio Selection 接口，不在阶段0训练或产生候选。

## 1. 审计边界与只读保证

- `data/` 仅执行 `find`、`du`、`stat`、`sha256sum` 和 `unzip -Z -1` 一类只读命令。
- 未解压任何 ZIP，未读取大型 CSV 的全量内容，未删除、移动或改写原始数据。
- 原始文件在操作系统权限层面是 `root:root` 且当前用户可写；“只读”是本项目流程约束，不是文件系统强制保护。后续脚本必须显式拒绝向 `data/` 写入。
- 未启动训练、特征提取、序列生成、序列优化或任何实验相关工作。

## 2. 规则核验状态

| 项目 | 当前结论 | 证据与置信边界 |
|---|---|---|
| 初赛任务 | 标准数据集上的抗原条件亲和力预测与候选排序 | 官网已确认；初赛不直接生成候选 |
| 初赛周期 | 2026-04-01 至 2026-08-07 | 官网已确认 |
| 晋级规模 | 20 支队伍进入第二阶段 | 官网已确认 |
| 排序方向 | 根据预测亲和力高低排序 | 官网已确认任务；原始字段方向及提交 Rank 方向仍需数据字典/模板确认 |
| 评价指标 | Spearman correlation | 官网已确认；精确评测实现仍待确认 |
| 提交字段 | 方案称 `VH/VHH、VL、Rank` | 仅来自 `idea.md`；需官方模板确认列名、编码和空值规范 |
| 常规抗体/纳米抗体规则 | 方案称常规项含 VH+VL，VHH 的 VL 为空 | 仅来自 `idea.md`；需官方原文确认 |
| 最终测试集与分组 | 未确认 | 本地没有测试集说明、分组键或评测脚本 |

结论：排序任务与 Spearman 已是官方确认事实；提交 schema、原始亲和力字段方向、并列处理和 Spearman 聚合实现仍不能写死为不可配置常量。完整第二阶段规则见 `阶段0_官方规则补充核验.md`，机器可读规则见 `configs/competition.yaml`。

## 3. 数据目录证据

### 3.1 外层目录与占用

| 路径 | 磁盘占用（`du -h`） | 观察 |
|---|---:|---|
| `data/` | 31G（精确文件和 30.405 GiB） | 122 个文件、27 个目录、0 个符号链接 |
| `data/初赛-序列数据/` | 2.4G | 22 个编号来源目录；外层 83 CSV、21 PDF |
| `data/初赛-结构数据/` | 6.9G | `sabdab_summary_all.tsv` 与结构 ZIP |
| `data/初赛-纳米抗体数据/` | 22G | 2 个 XLSX 与 12 个 INDI2 ZIP 分片 |

### 3.2 外层文件类型

| 扩展名 | 数量 | 说明 |
|---|---:|---|
| CSV | 83 | 序列/标签类表格；本阶段未全表读取 |
| PDF | 21 | 配套论文，不等同于赛事规则 |
| ZIP | 13 | 1 个结构包、12 个 INDI2 分片 |
| XLSX | 2 | ANDD 文件 |
| TSV | 1 | `sabdab_summary_all.tsv` |
| MD | 1 | 数据集卡片，只有许可和下载提示 |
| `.gitattributes` | 1 | Git 属性文件 |

### 3.3 大文件与压缩包索引

- 最大文件是 `all_structures_030526.zip`：7,295,960,590 bytes，中央目录含 31,554 条记录，其中 31,550 个 `.pdb`。
- 12 个 INDI2 ZIP 合计约 22G；单包约 1.43–2.00 GiB，中央目录条目数依次为 404、1410、103、22、2688、15、20、2991、528、83、488、319，总计 **9,071**。
- INDI2 索引中可见 360 个 Parquet 条目，另有 JSON、CSV、TSV、TXT、GZ 和 CRC；这些是包内条目，不计入外层 122 个文件。
- 最大外层 CSV 包括 `li2023machine_scFv-SARS-CoV-2_affinity2.csv`（约 1.05 GiB）、对应 `affinity1.csv`（约 702 MiB）与 `AbRank_dataset.csv`（约 284 MiB）。后续应使用分块/列投影读取。

### 3.4 数据证据的限制

`idea.md` 含有行数、标签分层和重复关系等先验审计结论，但阶段0没有重新扫描 CSV/XLSX 内容，因此本报告不把那些数字当作本阶段独立复核结果。阶段1必须生成逐文件 schema、行数、缺失率、标签取值与序列合法性清单。

## 4. 工程环境证据

| 资源 | 审计结果 | 阶段影响 |
|---|---|---|
| OS/内核 | Ubuntu 22 系，Linux 6.5.0-28，x86_64 | 常规 Linux 工具链可用 |
| Python | 3.11.7，`/root/anaconda3/bin/python` | 后续锁定依赖前先建立项目环境清单 |
| PyTorch | 2.2.2，编译 CUDA 12.1 | 沙箱外 CUDA 初始化成功 |
| GPU/CUDA | 1× NVIDIA GeForce RTX 4090；49,140 MiB；驱动 550.78；驱动支持 CUDA 12.4；沙箱外 PyTorch 可见 | 可支持后续 embedding/训练；正式运行需使用已映射 GPU 设备的执行上下文 |
| GPU 隔离差异 | 受限审计进程没有 `/dev/nvidia*`，其中 PyTorch 报 GPU 0；宿主进程可见 GPU | 环境验收必须在实际训练执行上下文重复，不可只依赖沙箱结果 |
| CPU | Intel Xeon Platinum 8575C，8 逻辑 CPU（4 核/8 线程） | 可做并行审计，线程数建议 4–6 |
| 内存 | 15 GiB，总可用约 13 GiB；swap 3.7 GiB | 大 CSV 必须分块，避免全量 DataFrame |
| 磁盘 | 196G 总量，63G 已用，134G 可用；inode 约 1% 使用 | 足够阶段1索引；不足以无计划展开全部结构与多套 embedding |
| Git | `/root/BioOS` 不是 Git 仓库 | 无法给出分支、提交或 dirty 状态；应在用户确认后初始化或接入现有仓库 |

## 5. 排序模型原理与 Spearman

模型对每个既有候选记录输出一个实数分数 `s_i`，仅用于决定候选间次序。推理时对 `s_i` 降序排序得到预测名次；模型接口不包含生成、编辑或搜索新字符串的能力。

后续可并行比较三类监督目标：

1. **Pointwise 基线**：预测规范化数值标签，工程简单，但与排名指标并不完全一致。
2. **Pairwise 排序**：对同一可比组中的 `(i,j)` 学习 `P(i ≻ j)`，例如 logistic/RankNet 损失。不能跨不兼容 assay 强造偏序，也不能把并列或截断标签当作强顺序。
3. **Listwise 排序**：以完整候选组为单位优化排序分布或可微排名近似，更贴近 Spearman，但批次构造、组大小和显存要求更高。

Spearman 等于两个名次变量的 Pearson correlation。一般定义为：

\[
\rho_s = \operatorname{corr}(R(y), R(\hat y))
= \frac{\operatorname{cov}(R(y),R(\hat y))}{\sigma_{R(y)}\sigma_{R(\hat y)}}.
\]

在没有并列名次时，也可写为：

\[
\rho_s = 1 - \frac{6\sum_{i=1}^{n}d_i^2}{n(n^2-1)},
\quad d_i = R(y_i)-R(\hat y_i).
\]

有并列值时应先用明确的 rank 方法（通常平均名次）再计算 Pearson correlation，不能盲用无并列简式。还须确认官方评测是对全体候选一次计算、按靶点分别计算后平均，还是其他聚合方式；这会改变验证代码。

### 5.1 初赛主线与第二阶段预留接口

初赛主线固定为：

```text
官方数据
→ 清洗、去重与按抗原/家族/聚类/结构同源关系的防泄漏划分
→ 共享抗原—抗体预训练编码器与交互融合
→ Affinity Ranking Head
→ 候选排名与 Spearman 验证
```

至少在相同固定折上比较 MSE/Huber 回归基线、pairwise ranking loss、listwise ranking loss、回归与排序联合损失。初赛以序列模型为主，结构特征只在覆盖与质量足够时作为增强。单张 48GB GPU 下优先冻结编码器训练排序头，再通过消融决定是否解冻最后若干层；LoRA 只有在目标编码器结构、显存和吞吐实测支持时才采用。监督任务是排序/数值微调，不是生成式 SFT。

第二阶段以虚线预留 ELISA Binding 概率头、Expression 排序/回归头、Aggregation 风险头、Novelty/合法性过滤接口，以及每队最多 6 个候选的 Portfolio Selection 接口。最终靶标状态为 `pending_official_release`；官网 Nipah virus G protein 展示仅为案例。没有相应标签时不得训练这些头，也不得伪造结果。

## 6. 后续纯计算实现路径

| 阶段 | 输入 | 核心工作 | 输出 | 验收重点 |
|---|---|---|---|---|
| 1 数据审计 | `data/` 表格和 ZIP 索引 | schema、行数、标签语义、字符合法性、缺失与重复概览 | `processed/inventory.*`、审计报告 | 原始区零写入；统计可复现 |
| 2 标签规范化 | 审计清单、标签注册表 | 单位/方向/截断/assay 分层；只做数值变换 | 规范化标签表、数据字典 | 每个变换可追溯；不跨语义强合并 |
| 3 去重与切分 | 规范化记录、字符串哈希、来源/母本/结构组 | 精确/近重复组件；grouped/source-held-out/antigen-cold 切分 | `splits/*.parquet`、泄漏检查 | 组件不跨折；固定随机种子 |
| 4 编码器特征 | 已存在字符串、固定 split | 预训练编码器只读推理，分块缓存 heavy/light/antigen 表征 | `embeddings/` 清单与张量 | 无训练、无字符串生成；缓存含模型版本和哈希 |
| 5 排序模型 | embeddings、标签、split | MSE/Huber；pairwise；listwise；联合损失 | `checkpoints/`、折外预测 | pair 仅在可比组；固定折消融；训练日志完整 |
| 6 严格交叉验证 | 折外预测、真实标签 | 全局/macro Spearman、Pearson、RMSE/MAE、Top-k、来源/类型/区间分组、泄漏哨兵 | `reports/cv_*` | 只用 OOF 选模；官方口径与 Top-k 定义可配置 |
| 7 排名集成与提交 | 多模型 OOF/测试分数 | percentile/rank averaging、稳定性检查、格式校验 | `submissions/*.csv` | 连续名次、无重复/缺失、schema 符合官方模板 |

## 7. 通用多任务数值评分接口预留

接口只接收已有记录并返回数值，不暴露序列生成或优化方法：

```python
class RankingScorer(Protocol):
    def encode(self, batch: ExistingRecordBatch) -> FeatureBatch: ...
    def score(self, features: FeatureBatch, task: TaskSpec) -> ScoreBatch: ...
    def rank(self, scores: ScoreBatch, group_ids: ArrayLike) -> RankBatch: ...

class TaskSpec(TypedDict):
    name: str             # kd, ic50, ec50, binding, custom_numeric
    direction: str        # higher_is_better / lower_is_better
    transform: str        # identity / log / registered transform
    comparable_group: str # 明确可比较域
```

所有实现需满足：输入字符串不可变；输出仅为分数/名次；任务方向和变换来自版本化配置；训练、验证与推理共享同一 schema；禁止将文件名、论文 ID 等高泄漏标识作为高容量特征。

## 8. 资源预算

| 工作项 | CPU/内存建议 | 磁盘预算 | GPU预算 |
|---|---|---:|---|
| 阶段1目录与表格审计 | 4–6 线程，峰值 ≤10 GiB，CSV 分块 | 2–10 GiB | 无 |
| 标签表、哈希与切分 | 4–6 线程，峰值 ≤12 GiB | 10–30 GiB | 无 |
| 预训练 embedding | 4–6 个 CPU 数据加载线程，主存峰值 ≤12 GiB | 需先按样本数×维度估算；建议预算上限 60 GiB 并支持分片 | 1× RTX 4090（49,140 MiB）；先按编码器做 batch-size 探测 |
| 排序训练与多折验证 | 数据加载峰值 ≤12 GiB | checkpoints/logs 20–50 GiB 上限 | 1× RTX 4090；折间串行，混合精度与显存峰值须记录 |
| 提交与报告 | 2–4 线程 | <5 GiB | 无 |

当前 134 GiB 可用空间必须保留至少 30 GiB 安全余量；禁止全量展开 7.3GB 结构 ZIP 或 12 个 INDI2 包，除非阶段计划和空间核算另行获批。

## 9. 主要风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 官方规则仍有实现空白 | 并列、聚合、提交格式或字段方向理解错误 | 已版本化 `competition.yaml`；未知项保持 pending，等待评测脚本/数据字典 |
| 标签单位/方向异质 | 排序对反向或不可比 | 文件级标签注册表；默认 quarantine |
| 重复/母本/结构泄漏 | CV 虚高 | 先建连接组件再分组切分；泄漏单测 |
| 并列与截断标签 | Spearman/排序损失失真 | 平均名次、弱化或跳过不确定 pair |
| 沙箱与宿主 GPU 可见性不同 | 在错误上下文启动任务会误报无卡或失败 | 训练前在目标执行上下文运行 `nvidia-smi` 与 PyTorch CUDA smoke test；记录设备与驱动 |
| 内存与磁盘不足 | OOM、空间耗尽 | 分块、列投影、分片缓存、预算闸门 |
| 原始区可写 | 误改数据 | 代码路径守卫、只读打开、哈希/mtime 清单 |
| Git 尚未建立 | 变更不可追溯 | 用户确认后初始化或连接正确仓库 |

## 10. 阶段0验收条件

- [x] 已阅读 `idea.md`，并区分方案陈述与独立证据。
- [x] 已统计目录、文件数、类型、占用和 ZIP 中央目录；未解压。
- [x] 已检查 Python、PyTorch、CUDA/GPU、CPU、内存、磁盘。
- [x] 已检查 Git；结论为当前路径不是仓库。
- [x] 已建立所有非原始数据目录。
- [x] 已定义后续七个纯计算模块及其输入、输出和验收门。
- [x] 已预留只评分/排序的通用多任务接口，明确不含生成与优化能力。
- [x] 已生成三张 SVG 与 PNG 图，并进行基本可读性检查。
- [x] 已用赛事官方全文确认初赛排序任务、Spearman、赛程、晋级规模与第二阶段核心规则。
- [x] 已建立 `configs/competition.yaml`，未知实现细节保持 pending。
- [ ] 官方评测实现、提交模板、最终数据字典和资源上限仍待确认。

## 11. 尚未确认的赛事信息

1. Spearman 的精确实现：全局或分组、分组权重、并列名次、常数数组与缺失值处理。
2. 真实标签原始方向与提交 Rank 方向是否完全一致。
3. 官方提交模板的精确列名、顺序、编码、空值和重复候选规则。
4. 训练/外部数据/预训练权重许可、联网限制与最终运行环境。
5. 测试候选是否包含抗原字段、多个靶点、VHH 与 VH/VL 混合，以及分组标识。
6. 提交次数、模型大小、推理时限、CPU/GPU/内存/磁盘上限。
7. 第二阶段最终抗原与最终数据字典；当前 `final_target_status: pending_official_release`。
8. 第二阶段三项原始指标方向、并列排名、`N=1` 与无效结果的评测实现细节。
9. 是否要求权重、容器、日志、随机种子或离线可复现包。

阶段0到此停止；未开始阶段1或任何模型训练。
