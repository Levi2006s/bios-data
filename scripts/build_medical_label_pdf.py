"""Create a printable Chinese PDF for manual label-direction review."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def font_path() -> Path:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("No supported Chinese font found in C:\\Windows\\Fonts")


def metric_text(metric: str) -> str:
    return {
        "KD": "抗体-抗原解离常数（KD）",
        "negative_log10_KD": "KD 的负对数亲和力分数",
        "log10_KD_or_IC50": "KD/IC50 的对数值",
        "predicted_log10_KD": "模型预测的 KD 对数值",
        "IC50": "产生一半抑制/中和效果的浓度",
        "EC50": "产生一半效应的浓度",
        "binding_class": "是否能够结合抗原（0/1）",
        "binding_signal": "实验检测到的相对结合信号",
        "none": "没有可直接使用的实验标签",
    }.get(metric, metric)


def direction_text(row: dict[str, str]) -> str:
    if row["direction"] == "0":
        return "不比较好坏"
    if row["metric"] == "binding_class":
        return "1 更好"
    return "越小越好" if row["direction"] == "-1" else "越大越好"


def reason_text(metric: str) -> str:
    if metric == "KD":
        return "KD 越小，抗体越不容易从抗原上脱离，通常表示结合更牢。"
    if metric == "negative_log10_KD":
        return "原始 KD 越小越好；取负对数后方向翻转，所以该分数越大越好。"
    if metric == "log10_KD_or_IC50":
        return "只取对数、没有加负号，所以仍然越小越好；不同实验类型不能直接混比。"
    if metric == "predicted_log10_KD":
        return "它估计的是 KD，因此越小越好；但这是模型预测，不等同于湿实验结果。"
    if metric in {"IC50", "EC50"}:
        return "达到相同效果所需浓度越低，通常说明效力越强。"
    if metric == "binding_class":
        return "1 表示实验判断为能够结合，0 表示不能结合。"
    if metric == "binding_signal":
        return "在该论文的实验定义中，信号越强表示检测到的结合越明显。"
    return "没有监督标签，仅作为辅助序列数据。"


def tier_text(tier: str) -> str:
    return {
        "Gold": "高可信\n实验标签",
        "Silver": "中等可信\n需同类比较",
        "Weak": "弱标签\n模型预测",
        "Auxiliary": "辅助数据\n无监督标签",
    }[tier]


def footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("MedicalCN", 8)
    canvas.setFillColor(colors.HexColor("#5B6573"))
    canvas.drawString(15 * mm, 8 * mm, "Bio-OS 人工标签方向审核表（医学生易读版）")
    canvas.drawRightString(landscape(A4)[0] - 15 * mm, 8 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def build(registry_path: Path, output_path: Path) -> None:
    pdfmetrics.registerFont(TTFont("MedicalCN", str(font_path()), subfontIndex=0))
    with registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["source_group"]].append(row)
    directions = Counter(row["direction"] for row in rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(A4)
    doc = SimpleDocTemplate(
        str(output_path), pagesize=(page_width, page_height),
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=13 * mm, bottomMargin=14 * mm,
        title="人工标签方向审核表（医学生易读版）",
        author="Bio-OS data curation team",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleCN", parent=styles["Title"], fontName="MedicalCN", fontSize=22,
                           leading=28, textColor=colors.HexColor("#17324D"), alignment=TA_CENTER)
    h1 = ParagraphStyle("H1CN", parent=styles["Heading1"], fontName="MedicalCN", fontSize=15,
                        leading=20, textColor=colors.HexColor("#0B6E69"), spaceBefore=8, spaceAfter=7)
    h2 = ParagraphStyle("H2CN", parent=styles["Heading2"], fontName="MedicalCN", fontSize=11,
                        leading=15, textColor=colors.HexColor("#17324D"), spaceBefore=6, spaceAfter=4)
    body = ParagraphStyle("BodyCN", parent=styles["BodyText"], fontName="MedicalCN", fontSize=9.5,
                          leading=14, textColor=colors.HexColor("#283442"), spaceAfter=5)
    note = ParagraphStyle("NoteCN", parent=body, fontSize=8.5, leading=12,
                          backColor=colors.HexColor("#EDF7F5"), borderPadding=6)
    cell = ParagraphStyle("CellCN", parent=body, fontSize=7.2, leading=9.4, spaceAfter=0)
    cell_center = ParagraphStyle("CellCenterCN", parent=cell, alignment=TA_CENTER)

    story = [
        Paragraph("人工标签方向审核表", title),
        Paragraph("医学生易读版 · 覆盖全部 83 个 CSV 文件", h2),
        Spacer(1, 4 * mm),
        Paragraph("这份表只回答一个问题：每个文件里的标签数字，究竟是越大越好，还是越小越好？", note),
        Spacer(1, 4 * mm),
        Paragraph("先理解四个概念", h1),
        Paragraph("<b>KD：</b>可以理解为抗体和抗原分开有多容易。KD 越小，通常结合越牢。例如 1 nM 通常优于 100 nM。", body),
        Paragraph("<b>IC50 / EC50：</b>达到一半抑制、中和或效应所需的浓度。达到相同效果需要的浓度越低，通常效力越强。", body),
        Paragraph("<b>-log10(KD)：</b>由于加了负号，方向会翻转，分数越大反而代表原始 KD 越小。", body),
        Paragraph("<b>实验标签与预测标签：</b>实验标签来自 SPR、细胞实验、展示筛选或中和实验；预测标签只是另一个模型算出的结果，不能当成实验事实。", body),
        Paragraph("总体审核结果", h1),
        Paragraph(
            f"共 {len(rows)} 个文件：{directions['1']} 个越大越好，{directions['-1']} 个越小越好，"
            f"{directions['0']} 个没有可直接比较好坏的标签。", body
        ),
        Paragraph("优先复核", h1),
        Paragraph(
            "来源 4（AbRank）的 fitness 实为 log10(KD/IC50)，应越小越好；来源 9 的连续 KD 虽标为 M，"
            "但论文和值域支持 nM；来源 3、6 为模型预测弱标签；来源 12 为相对结合信号；来源 17 有 3 条异常 KD 已隔离。",
            note,
        ),
        PageBreak(),
        Paragraph("逐文件审核表", title),
        Paragraph("在最后一列勾选“同意”，或写下修改意见。", body),
    ]

    header = ["文件", "医学含义", "正确方向", "判断理由", "可信程度", "审核"]
    widths = [52 * mm, 39 * mm, 25 * mm, 69 * mm, 31 * mm, 28 * mm]
    for group in sorted(groups, key=lambda value: int(value.replace("\\", "/").split("/")[-1])):
        group_rows = sorted(groups[group], key=lambda row: row["source_file"])
        first = group_rows[0]
        story.append(KeepTogether([
            Paragraph(group, h1),
            Paragraph(f"对应论文：{first['paper_title']}（{first['publication_year']}）", body),
        ]))
        table_rows = [[Paragraph(text, cell_center) for text in header]]
        for row in group_rows:
            table_rows.append([
                Paragraph(Path(row["source_file"]).name, cell),
                Paragraph(metric_text(row["metric"]), cell),
                Paragraph(direction_text(row), cell_center),
                Paragraph(reason_text(row["metric"]), cell),
                Paragraph(tier_text(row["tier"]).replace("\n", "<br/>"), cell_center),
                Paragraph("□ 同意<br/>□ 修改：<br/><br/>", cell),
            ])
        table = Table(table_rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "MedicalCN"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176B68")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A9B5C2")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([table, Spacer(1, 3 * mm)])

    story.extend([
        PageBreak(),
        Paragraph("审核签字", title),
        Spacer(1, 8 * mm),
        Paragraph("审核人：________________________________________________________", body),
        Spacer(1, 7 * mm),
        Paragraph("审核日期：______________________________________________________", body),
        Spacer(1, 7 * mm),
        Paragraph("总体结论：　□ 全部同意　　□ 有修改（已在表中注明）", body),
        Spacer(1, 9 * mm),
        Paragraph("其他备注：", h1),
        Spacer(1, 35 * mm),
        Paragraph("____________________________________________________________________________________________", body),
        Spacer(1, 7 * mm),
        Paragraph("____________________________________________________________________________________________", body),
    ])
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("configs/label_registry.csv"))
    parser.add_argument("--output", type=Path, default=Path("output/pdf/人工标签方向审核表_医学生易读版.pdf"))
    args = parser.parse_args()
    build(args.registry, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
