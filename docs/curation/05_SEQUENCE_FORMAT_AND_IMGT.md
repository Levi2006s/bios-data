# 05 - 抗体统一格式与 IMGT 编号准备

## 模块简介

本模块统一重链、轻链、抗原和 CDRH3 的字符格式，并准备可交给专业编号工具的 FASTA。不会用手写规则伪造 IMGT 编号。

## 已完成内容

- 序列统一为大写氨基酸字母；
- 空格、分隔符和大小写被标准化；
- 重链非法时隔离；
- 轻链、抗原、CDRH3 允许缺失；
- 含 `X` 的 1,874 条轻链被标为 ambiguous，保留重链但不假装轻链有效；
- 生成覆盖 82 个有监督文件的 3,964 行可复现标准化样例；
- 生成 2,110 条去重后的 H/L 链 FASTA，作为 IMGT 编号验证批次。

样例输出字段为：`record_id, source_group, source_file, antigen_id, antigen_seq, heavy, light, cdrh3, raw_label, direction, score`。其中 `score` 是来源内部百分位，恒定为“越大越好”。

## IMGT 状态

FASTA 输入已经完成，但本机没有安装 ANARCII，因此没有伪造编号结果。ANARCII 是当前可安装的专业抗原受体编号工具，可输出 IMGT 编号；官方说明见 [ANARCII](https://pypi.org/project/anarcii/) 和 [ANARCI/IMGT 编号说明](https://github.com/oxpig/ANARCI)。

云端安装后可对 `imgt_numbering_input.fasta` 执行 IMGT scheme。对全量数据应先按链序列去重，再编号 277,515 个精确抗体组合中的唯一链，避免对重复记录反复计算。

```powershell
pip install -e ".[numbering]"
```

该可选依赖固定为 `anarcii==2.0.5`。它还会安装 PyTorch，体积明显大于本项目的基础数据处理环境，因此没有在本机自动下载。

## 接口

```powershell
python -m bioos_benchmark.prepare `
  --data-root "<原始数据目录>" `
  --output data/processed/curation/curated_sample.csv `
  --max-rows-per-file 100 `
  --direction-overrides configs/direction_overrides.csv `
  --label-registry configs/label_registry.csv
```

输出：

- `data/processed/curation/curated_sample.csv`
- `data/processed/curation/imgt_numbering_input.fasta`
