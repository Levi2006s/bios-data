# Bio-OS 数据处理复现代码

本交付物只负责数据处理，不包含模型训练和抗体生成。

## 功能

1. `audit`：扫描全部CSV，输出字段、行数、可用记录数、标签列、方向猜测及序列完整度；
2. `prepare`：统一字段、清洗氨基酸序列、统一标签方向、来源内百分位标准化；
3. `split`：按整篇论文数据组进行确定性的训练/验证/测试拆分；
4. `validate`：检查字段、氨基酸、分数范围、重复ID和跨集合泄漏；
5. 所有步骤只使用Python标准库，不需要安装PyTorch、Pandas或Scikit-learn。

## 环境

- Python 3.10或更高版本；
- Windows、Linux均可；
- 原始下载目录保持只读；
- 建议为处理结果准备至少10 GB空间；本流程不要求解压INDI2或结构包。

## 一次运行全部步骤

### Windows PowerShell

```powershell
$env:PYTHONPATH = "src"

python -m bioos_benchmark.audit `
  --data-root "$HOME\Downloads\第四届Bio-OS开源大赛数据" `
  --output data\processed\audit.csv `
  --hash-inputs

python -m bioos_benchmark.prepare `
  --data-root "$HOME\Downloads\第四届Bio-OS开源大赛数据" `
  --output data\processed\benchmark.csv `
  --max-rows-per-file 5000 `
  --direction-overrides configs\direction_overrides.csv

python -m bioos_benchmark.split `
  --input data\processed\benchmark.csv `
  --output data\processed\benchmark_with_split.csv

python -m bioos_benchmark.validate `
  --input data\processed\benchmark_with_split.csv `
  --report data\processed\validation_report.json
```

### Linux

```bash
export PYTHONPATH=src

python -m bioos_benchmark.audit \
  --data-root /data/第四届Bio-OS开源大赛数据 \
  --output data/processed/audit.csv \
  --hash-inputs

python -m bioos_benchmark.prepare \
  --data-root /data/第四届Bio-OS开源大赛数据 \
  --output data/processed/benchmark.csv \
  --max-rows-per-file 5000 \
  --direction-overrides configs/direction_overrides.csv

python -m bioos_benchmark.split \
  --input data/processed/benchmark.csv \
  --output data/processed/benchmark_with_split.csv

python -m bioos_benchmark.validate \
  --input data/processed/benchmark_with_split.csv \
  --report data/processed/validation_report.json
```

## 输出文件

```text
data/processed/
├── audit.csv
├── audit.summary.json
├── benchmark.csv
├── benchmark.summary.json
├── benchmark_with_split.csv
├── benchmark_with_split.split_manifest.json
└── validation_report.json
```

`benchmark.csv`字段：

| 字段 | 说明 |
|---|---|
| record_id | 内容生成的稳定SHA-256短ID |
| source_group | 编号1～22的论文数据组 |
| source_file | 原始相对路径 |
| antigen_id | 抗原名称；缺失时使用文件名 |
| antigen_seq | 抗原序列，可为空 |
| heavy/light | 清洗后的重链/轻链 |
| cdrh3 | 原文件明确提供时保留 |
| raw_label | 原始数值标签 |
| direction | `1`为原值越大越好，`-1`为越小越好 |
| score | 来源文件内部0～1百分位，越大越好 |
| split | 仅拆分文件包含，取train/validation/test |

## 人工方向审核

自动方向只依据列名，是初步规则。阅读对应论文后，在`configs/direction_overrides.csv`加入：

```csv
source_file,direction,verified_by,notes
初赛-序列数据/示例/example.csv,-1,论文页码,原始KD越小越好
```

程序以人工覆盖值为准。正式比赛前应把所有进入训练的文件都审核一遍。

## 采样

`--max-rows-per-file 5000`表示每个CSV最多保留5000条。程序使用固定种子的蓄水池采样，扫描一遍文件并保证每行被选中的概率相同。设为`0`表示保留所有可用记录。

## AI 模块双路线并行开发

组内计算机同学和数学同学的两条并行模型路线、公共数据接口、六个模块说明和模块文档模板位于：

```text
docs/parallel_ai/README.md
```

- 计算机路线：冻结蛋白语言模型表征、三路深度排序器、训练与推理；
- 数学路线：质量加权偏好图、可解释排序模型、严格评价与集成。

两条路线统一输出 `record_id + score`，可以独立评价，也可以在最后进行百分位排名集成。开始实现前，两位同学应先共同确认 `docs/parallel_ai/SHARED_INTERFACES.md`。

## 测试

数据处理代码本身只依赖标准库。测试工具可单独安装：

```bash
python -m pip install pytest
pytest -q tests/test_data_pipeline.py
```

正式复现时应记录Python版本、原始文件SHA-256、方向覆盖表、随机种子和所有输出的哈希值。
