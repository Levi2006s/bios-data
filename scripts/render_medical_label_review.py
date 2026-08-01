"""Render the label registry in language suitable for medical students."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def esc(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def plain_metric(row: dict[str, str]) -> str:
    metric = row["metric"]
    if metric == "KD":
        return "抗体与抗原分开的难易程度（KD）"
    if metric == "negative_log10_KD":
        return "把 KD 取负对数后的亲和力分数"
    if metric == "log10_KD_or_IC50":
        return "KD 或 IC50 取对数后的数值"
    if metric == "predicted_log10_KD":
        return "模型预测的 KD 对数值（不是实验结果）"
    if metric == "IC50":
        return "抑制或中和一半目标所需浓度（IC50）"
    if metric == "EC50":
        return "达到一半效果所需浓度（EC50）"
    if metric == "binding_class":
        return "是否能够与抗原结合（0/1）"
    if metric == "binding_signal":
        return "实验检测到的相对结合信号"
    if metric == "none":
        return "没有可直接使用的实验标签"
    return metric


def plain_direction(row: dict[str, str]) -> str:
    direction = row["direction"]
    metric = row["metric"]
    if direction == "0":
        return "不比较好坏"
    if metric == "binding_class":
        return "1 更好：1=能结合，0=不能结合"
    if direction == "-1":
        return "数值越小越好"
    return "数值越大越好"


def medical_reason(row: dict[str, str]) -> str:
    metric = row["metric"]
    if metric == "KD":
        return "KD 越小，抗体越不容易从抗原上脱离，通常表示结合越强。"
    if metric == "negative_log10_KD":
        return "原始 KD 本来越小越好；取负对数后方向翻转，所以分数越大越好。"
    if metric == "log10_KD_or_IC50":
        return "这里只取了对数，没有加负号，因此仍然是越小越好。不同实验类型不能直接混比。"
    if metric == "predicted_log10_KD":
        return "它估计的是 KD，因此越小越好；但这是模型预测，只能当辅助信息。"
    if metric in {"IC50", "EC50"}:
        return "达到同样效果需要的药物/抗体浓度越低，说明效力通常越强。"
    if metric == "binding_class":
        return "数据集已经把实验结果整理成是否结合，1 表示结合。"
    if metric == "binding_signal":
        return "在该论文的实验定义中，信号越强代表检测到的结合越明显，但它不是绝对亲和力。"
    return "没有监督标签，只能作为辅助序列数据。"


def plain_tier(row: dict[str, str]) -> str:
    return {
        "Gold": "高可信：主要来自明确的实验测量",
        "Silver": "中等可信：实验来源明确，但指标或单位不完全统一",
        "Weak": "弱标签：来自模型预测，不等同于实验真值",
        "Auxiliary": "辅助数据：没有可直接训练的标签",
    }[row["tier"]]


def render(registry_path: Path, output_path: Path) -> None:
    with registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["source_group"]].append(row)
    directions = Counter(row["direction"] for row in rows)

    lines = [
        "# 人工标签方向审核表（医学生易读版）",
        "",
        "> 这份表回答一个核心问题：每个数据文件里的数字，到底是越大越好，还是越小越好？",
        "",
        "## 一、先理解四个常见概念",
        "",
        "### 1. KD：结合有多牢",
        "",
        "KD 可以简单理解成抗体和抗原“分开有多容易”。**KD 越小，通常结合越牢，亲和力越强。**例如 1 nM 通常优于 100 nM。",
        "",
        "### 2. IC50 和 EC50：需要多少浓度才能产生一半效果",
        "",
        "如果达到相同效果只需要更低浓度，一般说明效力更强。因此 **IC50、EC50 通常越小越好**。但它们描述的是功能效果，不完全等同于 KD。",
        "",
        "### 3. 为什么有些 KD 分数反而越大越好",
        "",
        "有些作者会计算 `-log10(KD)`。因为前面加了负号，方向发生翻转：**这种分数越大，代表原始 KD 越小，也就是越好。**",
        "",
        "### 4. 实验标签和预测标签不能等同",
        "",
        "实验标签来自 SPR、细胞实验、酵母展示或中和实验；预测标签是另一个模型算出来的结果。预测标签可以帮助扩大数据量，但不能当成真正的实验结论。",
        "",
        "## 二、总体结论",
        "",
        f"- 共审核 {len(rows)} 个 CSV 文件；",
        f"- {directions['1']} 个文件是“数值越大越好”；",
        f"- {directions['-1']} 个文件是“数值越小越好”；",
        f"- {directions['0']} 个文件没有可直接比较好坏的标签。",
        "",
        "## 三、最需要注意的六组数据",
        "",
        "- **来源 4（AbRank）**：虽然字段叫 `fitness`，实际保存的是 KD/IC50 的对数，仍然应该越小越好。",
        "- **来源 9**：连续 KD 文件的列名标成 M，但论文和数值大小更符合 nM；方向是越小越好。",
        "- **来源 3、6**：标签是模型预测结果，不是湿实验结果，列为弱标签。",
        "- **来源 12**：标签是相对结合信号，不是 KD，只适合同一实验内比较。",
        "- **来源 17**：有 3 条 KD 为零或明显超出合理范围，已经隔离。",
        "- **来源 22**：没有可直接使用的数值标签，不进入监督训练。",
        "",
        "## 四、逐文件审核",
        "",
    ]

    for group in sorted(groups, key=lambda value: int(value.replace("\\", "/").split("/")[-1])):
        group_rows = sorted(groups[group], key=lambda row: row["source_file"])
        first = group_rows[0]
        lines.extend([
            f"### {esc(group)}",
            "",
            f"对应论文：{esc(first['paper_title'])}（{esc(first['publication_year'])}）",
            "",
            "| 文件 | 这个数字表示什么 | 哪个方向更好 | 为什么 | 可信程度 | 你的审核 |",
            "|---|---|---|---|---|---|",
        ])
        for row in group_rows:
            lines.append(
                "| " + " | ".join([
                    f"`{esc(Path(row['source_file']).name)}`",
                    esc(plain_metric(row)),
                    esc(plain_direction(row)),
                    esc(medical_reason(row)),
                    esc(plain_tier(row)),
                    "□ 同意　□ 修改：",
                ]) + " |"
            )
        lines.append("")

    lines.extend([
        "## 五、审核完成后怎么反馈",
        "",
        "如果你认为某一行有问题，只需要告诉我：来源编号、文件名、你认为正确的方向，以及依据。例如：",
        "",
        "> 来源 4，AbRank_dataset.csv，我认为应为越小越好，因为 fitness 是 log10(KD)。",
        "",
        "- 审核人：",
        "- 审核日期：",
        "- 总体结论：□ 同意　□ 需要修改",
        "",
        "## 六、重新生成本文档",
        "",
        "```powershell",
        "python scripts/render_medical_label_review.py `",
        "  --registry configs/label_registry.csv `",
        "  --output docs/curation/MANUAL_LABEL_DIRECTION_REVIEW_MEDICAL.md",
        "```",
        "",
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("configs/label_registry.csv"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("docs/curation/MANUAL_LABEL_DIRECTION_REVIEW_MEDICAL.md"),
    )
    args = parser.parse_args()
    render(args.registry, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
