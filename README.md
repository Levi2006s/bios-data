# 第四届 Bio-OS 抗体设计基准：可复现起步方案

本项目把赛事提供的异构公开数据整理为统一的抗体序列基准，并提供一条可以在普通电脑上冒烟测试、在云端扩展训练的完整流程：

```text
原始CSV → 字段/方向统一 → 来源内百分位标签 → 来源级训练/测试拆分
       → 序列基线训练 → 多维评价 → CDR-H3候选生成与排序
```

> 重要边界：本仓库的候选生成器是用于验证工程流程的“局部突变基线”，不是经过实验验证的中和抗体设计系统。最终参赛版应接入 IgLM、IgGM、dyMEAN 或 RFantibody，并使用结构模型和实验数据进一步验证。

## 1. 数据认识

赛事下载目录中目前包含：

- 序列数据：83 个 CSV、约 460 万行，另有 21 篇配套论文；
- 纳米抗体数据：ANDD 索引 30,333 条，INDI2 压缩分卷约 22.8 GB；
- 结构数据：SAbDab 摘要和 31,550 个 PDB，压缩包约 7.3 GB。

不同来源的 `fitness` 不能直接比较：`-log(KD)` 越大越好，而原始 `KD/IC50/EC50` 越小越好。更重要的是，KD、IC50、EC50、二分类、OVA 风险和 ADCC 不是同一个任务。本项目依据人工认证表把它们分到独立训练头，再在兼容的实验范围内建立百分位或偏好对。

## 2. 云端环境安装

推荐 Ubuntu 22.04、Python 3.10。基础模型不要求 GPU：

```bash
git clone <your-repository-url>
cd ai-de-novo-design-1-benchmark
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

大型生成模型和结构模型应分别建立独立环境，不要与本基线混装。

## 3. 数据预处理

Windows PowerShell 示例：

```powershell
python -m bioos_benchmark.prepare `
  --data-root "$HOME\Downloads\第四届Bio-OS开源大赛数据" `
  --output data/processed/benchmark.csv `
  --max-rows-per-file 5000
```

Linux 云端示例：

```bash
python -m bioos_benchmark.prepare \
  --data-root /data/第四届Bio-OS开源大赛数据 \
  --output data/processed/benchmark.csv \
  --max-rows-per-file 50000
```

参数说明：

- `--max-rows-per-file 5000`：每个来源做确定性的蓄水池采样，避免超大数据集淹没小型实验数据；
- 设置为 `0`：使用所有可解析记录；
- 输出同时生成 `benchmark.summary.json`，记录来源、数量和跳过文件。

## 4. 训练与评价

```bash
python -m bioos_benchmark.train \
  --input data/processed/benchmark.csv \
  --artifact-dir artifacts/baseline
```

模型使用抗体重链、轻链和可用的抗原序列字符 k-mer，加上长度、疏水性、电荷和半胱氨酸等简单特征。测试集按完整论文数据组（编号1～22）留出，避免同一论文不同CSV中的重复候选或近似突变体同时进入训练和测试。

主要指标：

- Spearman：排序是否正确，作为主指标；
- Pearson：线性相关程度；
- RMSE、MAE：预测误差；
- Top-10% enrichment：预测前 10% 中富集了多少真正优良序列；
- macro-source Spearman：每个来源等权，避免大数据集控制总分。

输出：

```text
artifacts/baseline/model.joblib
artifacts/baseline/metrics.json
artifacts/baseline/predictions.csv
```

## 5. 生成和排序候选

```bash
python -m bioos_benchmark.design \
  --model artifacts/baseline/model.joblib \
  --target examples/target.json \
  --output artifacts/candidates.csv \
  --count 1000 \
  --max-mutations 3
```

输入 JSON 必须包含抗原序列、重链、轻链，以及重链中精确出现的 `cdrh3`。程序会生成局部变体、预测分数，并对潜在糖基化位点、过度疏水和异常半胱氨酸进行简单惩罚。

## 6. 如何升级成参赛模型

第一轮先保留当前预处理、拆分和评价框架，只替换模型：

1. 用抗体语言模型（BALM、IgBert/IgT5等）替代字符 k-mer；
2. 用抗原编码器加入抗原序列或表位表示；
3. 用 pairwise ranking loss 学习同一靶点内的相对优劣；
4. 用 IgLM 产生大规模 CDR 候选；
5. 用 AntiFold 检查序列—结构一致性；
6. 用 IgGM/dyMEAN/RFantibody评估抗原特异性和复合物结构；
7. 最后做可开发性、多样性和结构置信度的 Pareto 筛选。

详细里程碑见 `PLAN.md`，技术设计见 `docs/ALGORITHM_DESIGN.md`，训练说明见 `docs/TRAINING.md`。

## 7. 两位同学并行开发 AI 模块

计算机同学与数学同学的并行方案、公共数据接口、六个模块说明和模块文档模板，统一放在：

```text
docs/parallel_ai/README.md
```

两条路线分别独立输出 `record_id + score`，最后再做严格评价和百分位排名集成。开始编码前，两位同学应先共同确认 `docs/parallel_ai/SHARED_INTERFACES.md`。

## 8. 测试

```bash
pytest -q
```

所有随机过程都提供固定种子；原始数据只读，处理结果写入 `data/processed`；模型、指标和候选写入 `artifacts`。
