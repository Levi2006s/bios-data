# 代码运行环境与安装说明

## 推荐环境

- Ubuntu 22.04 x86_64
- Python 3.11.7
- NVIDIA GPU，建议显存 ≥16 GB；复现实验使用 RTX 4090 24 GB
- NVIDIA driver 550.78 或兼容 CUDA 12.1 的更新版本
- 训练需要 CUDA；数据处理与结果导出可使用 CPU

## Conda 安装

```bash
conda env create -f environment.yml
conda activate bioos-abcompass
pip install -e .
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
pytest -q
```

## venv/pip 安装

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements-lock.txt
pip install -e . --no-deps
pytest -q
```

## 预训练模型

固定使用：

```text
facebook/esm2_t30_150M_UR50D
revision a695f6045e2e32885fa60af20c13cb35398ce30c
```

首次运行需联网下载；之后可使用 Hugging Face 缓存。提交包不重复携带第三方模型缓存，以减小体积并遵守来源边界。项目携带由该固定版本生成的最终 ESM embedding 时，可跳过重复编码。

## 目录约定

```text
data/初赛-序列数据/     原始非 VHH 序列
data/processed/         最终可再生训练表
artifacts/final/        最终模型、聚类、指标和预测
deliverables/           技术文档清单与抗体序列
src/bioos_benchmark/    算法源码
scripts/                训练、融合、推理入口
tests/                  自动化测试
```

## 完整性检查

```bash
git status --short
python -m py_compile src/bioos_benchmark/*.py
pytest -q
sha256sum deliverables/antibody_sequences.csv.gz
```
