"""Render the reviewed label registry as a human-auditable Markdown document."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def esc(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def direction_text(value: str) -> str:
    return {"1": "+1（越大越好）", "-1": "-1（越小越好）", "0": "0（无监督标签）"}.get(value, value)


def render(registry_path: Path, output_path: Path) -> None:
    with registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["source_group"]].append(row)

    directions = Counter(row["direction"] for row in rows)
    tiers = Counter(row["tier"] for row in rows)
    lines = [
        "# 人工标签方向审核表",
        "",
        "> 用途：请团队成员逐文件审核标签的含义、单位和方向。此表只处理数据定义，不涉及模型训练。",
        "",
        "## 一、审核结论摘要",
        "",
        f"- 登记文件：{len(rows)} 个；",
        f"- `+1`（数值越大越好）：{directions['1']} 个；",
        f"- `-1`（数值越小越好）：{directions['-1']} 个；",
        f"- `0`（没有监督标签）：{directions['0']} 个；",
        f"- 数据等级：Gold {tiers['Gold']} 个、Silver {tiers['Silver']} 个、Weak {tiers['Weak']} 个、Auxiliary {tiers['Auxiliary']} 个。",
        "",
        "## 二、统一判断规则",
        "",
        "| 标签形式 | 正确方向 | 简单解释 |",
        "|---|---:|---|",
        "| 原始 KD/Kd | -1 | 解离常数越小，抗体与抗原结合越强 |",
        "| `log10(KD)` | -1 | 对 KD 取对数后仍然是越小越好 |",
        "| `-log10(KD)` / pKD | +1 | 加了负号，所以数值越大代表 KD 越小 |",
        "| IC50 / EC50 | -1 | 达到一半效果所需浓度越小越好 |",
        "| binder=1, non-binder=0 | +1 | 1 表示能够结合 |",
        "| 实验结合信号/富集度 | +1 | 只在论文确认信号越大代表结合越强时使用 |",
        "| 预测 `log10 KD(nM)` | -1 | 是模型预测的 KD，只作为 Weak 标签 |",
        "",
        "## 三、请优先审核的项目",
        "",
        "1. **来源 4 AbRank**：CSV 的 `fitness` 等于 `log10(KD/IC50)`，应为 `-1`，不是旧程序猜测的 `+1`。",
        "2. **来源 9 连续 KD 文件**：字段名写 `Kd [M]`，但论文和值域 3.3–2946.89 表明应按 nM 理解；方向仍为 `-1`。",
        "3. **来源 3 和 6**：`Pred_affinity` 是预测的 `log10 KD(nM)`，方向为 `-1`，等级为 Weak。",
        "4. **来源 12**：是相对 ANT/OVA binding signal，方向为 `+1`，但不是绝对 KD，因此列为 Silver。",
        "5. **来源 17**：原始 KD 方向为 `-1`；3 条零值或明显不合理数值已进入隔离，不参与普通监督数据。",
        "",
        "审核时若不同意某项，请直接在对应表格最后一列填写建议，例如：`改为 +1，原因：论文第 X 页……`。",
        "",
        "## 四、逐文件审核表",
        "",
    ]

    for group in sorted(groups, key=lambda value: int(value.replace("\\", "/").split("/")[-1])):
        group_rows = sorted(groups[group], key=lambda row: row["source_file"])
        first = group_rows[0]
        lines.extend([
            f"### {esc(group)}",
            "",
            f"论文：{esc(first['paper_title'])}（{esc(first['publication_year'])}）",
            "",
            "| 文件 | 选用标签列 | 指标与单位 | 方向 | 来源性质 | 等级 | 判断依据/备注 | 审核意见 |",
            "|---|---|---|---:|---|---|---|---|",
        ])
        for row in group_rows:
            filename = Path(row["source_file"]).name
            metric = f"{row['metric']}；{row['unit']}"
            evidence = row["evidence"]
            if row["notes"]:
                evidence += "；" + row["notes"]
            lines.append(
                "| " + " | ".join([
                    f"`{esc(filename)}`",
                    f"`{esc(row['selected_label_column']) or '—'}`",
                    esc(metric),
                    esc(direction_text(row["direction"])),
                    esc(row["label_origin"]),
                    esc(row["tier"]),
                    esc(evidence),
                    "□ 同意 / □ 修改：",
                ]) + " |"
            )
        lines.append("")

    lines.extend([
        "## 五、审核签字区",
        "",
        "- 审核人：",
        "- 审核日期：",
        "- 总体结论：□ 全部同意　□ 有修改（请在表中注明）",
        "- 其他备注：",
        "",
        "## 六、程序接口",
        "",
        "本文件由 `configs/label_registry.csv` 自动渲染。修改正式方向时，应先修改登记表或生成规则，再重新生成本文件，避免文档与代码不一致。",
        "",
        "```powershell",
        "python scripts/render_label_direction_review.py `",
        "  --registry configs/label_registry.csv `",
        "  --output docs/curation/MANUAL_LABEL_DIRECTION_REVIEW.md",
        "```",
        "",
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("configs/label_registry.csv"))
    parser.add_argument("--output", type=Path, default=Path("docs/curation/MANUAL_LABEL_DIRECTION_REVIEW.md"))
    args = parser.parse_args()
    render(args.registry, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
