"""Render the Stage-0 diagrams to PNG without network or SVG dependencies."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "visuals"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def font(size: int, bold: bool = False):
    # The CJK collection is used consistently; weight is expressed by size/color.
    return ImageFont.truetype(FONT, size=size, index=0)


INK, MUTED, BLUE, PALE, GOLD, WHITE, BG = (
    "#172033", "#526079", "#2D72B8", "#EEF5FC", "#C58A24", "#FFFFFF", "#F8FAFC"
)


def box(d, xy, title, lines, fill=WHITE, stroke="#9CB7D9", tag=None):
    d.rounded_rectangle(xy, radius=14, fill=fill, outline=stroke, width=3)
    x, y = xy[0] + 25, xy[1] + 22
    if tag:
        d.text((x, y), tag, font=font(18), fill="#1557A0")
        y += 38
    d.text((x, y), title, font=font(22), fill=INK)
    y += 40
    for line in lines:
        d.text((x, y), line, font=font(16), fill=MUTED)
        y += 30


def arrow(d, points):
    d.line(points, fill="#506784", width=4, joint="curve")
    x, y = points[-1]
    d.polygon([(x, y), (x - 14, y - 8), (x - 14, y + 8)], fill="#506784")


def dashed_line(d, points, fill="#7F8DA3", width=3, dash=12, gap=8):
    """Draw axis-aligned dashed segments for reserved-interface connectors."""
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 == x2:
            step = 1 if y2 >= y1 else -1
            for y in range(y1, y2, step * (dash + gap)):
                d.line((x1, y, x1, y + step * min(dash, abs(y2 - y))), fill=fill, width=width)
        elif y1 == y2:
            step = 1 if x2 >= x1 else -1
            for x in range(x1, x2, step * (dash + gap)):
                d.line((x, y1, x + step * min(dash, abs(x2 - x)), y1), fill=fill, width=width)


def road_map():
    im = Image.new("RGB", (1600, 900), BG); d = ImageDraw.Draw(im)
    d.text((70, 42), "阶段0后全流程路线图", font=font(40), fill=INK)
    d.text((70, 98), "只处理已有候选字符串：审计 → 规范化 → 无泄漏验证 → 排名文件", font=font(19), fill=MUTED)
    top = [(70,155,385,285),(465,155,780,285),(860,155,1175,285),(1215,155,1530,285)]
    box(d,top[0],"规则 / 数据目录 / 环境",["122 文件 · 30.405 GiB","1× RTX 4090 · 49,140 MiB"],tag="阶段0 · 已完成")
    box(d,top[1],"数据审计与标签规范化",["schema · 方向 · 单位","截断 · 质量层"],PALE,BLUE,"阶段1–2")
    box(d,top[2],"去重与无泄漏切分",["重复组件 · 来源留出","抗原冷启动"],PALE,BLUE,"阶段3")
    box(d,top[3],"规则与运行环境就绪",["官方口径 · GPU 映射","split 冻结"],"#FFF7E8",GOLD,"验收闸门")
    for a,b in zip(top,top[1:]): arrow(d,[(a[2],220),(b[0]-10,220)])
    low=[(135,410,450,540),(515,410,830,540),(895,410,1210,540),(1275,410,1530,540)]
    for xy,title,lines,tag in [
        (low[0],"预训练编码器特征",["只读推理 · 分片缓存","版本哈希"],"阶段4"),
        (low[1],"排序模型",["pointwise · pairwise","listwise"],"阶段5"),
        (low[2],"严格交叉验证",["OOF Spearman · 分组结果","稳健性"],"阶段6"),
        (low[3],"排名集成与提交",["rank average","schema QA"],"阶段7")]: box(d,xy,title,lines,PALE,BLUE,tag)
    arrow(d,[(1370,285),(1370,350),(292,350),(292,400)])
    for a,b in zip(low,low[1:]): arrow(d,[(a[2],475),(b[0]-10,475)])
    d.rounded_rectangle((70,685,1530,815),14,fill=WHITE,outline="#CBD5E1",width=2)
    d.text((100,710),"贯穿式约束",font=font(22),fill=INK)
    d.text((100,752),"原始数据只读 · 不生成/修改字符串 · 标签变换可追溯 · 组件不跨折 · 只用 OOF 选模 · 提交前独立校验",font=font(17),fill=MUTED)
    d.text((100,787),"当前停点：阶段0完成，等待用户确认。来源：本地审计（2026-07-26）。",font=font(16),fill=MUTED)
    im.save(OUT / "阶段0_全流程路线图.png")


def interface_map():
    im=Image.new("RGB",(1600,900),BG); d=ImageDraw.Draw(im)
    d.text((70,42),"通用多任务排序模型接口",font=font(40),fill=INK)
    d.text((70,98),"输入是已有候选记录；输出仅为数值分数和组内名次",font=font(19),fill=MUTED)
    box(d,(70,180,380,360),"ExistingRecordBatch",["heavy / vhh","light / antigen (optional)","record_id / group_id"])
    box(d,(70,470,380,650),"TaskSpec",["name / direction","transform","comparable_group"])
    box(d,(500,250,800,550),"RankingScorer",["encode(batch)","score(features, task)","rank(scores, groups)","共享编码器 + 任务评分头"],PALE,BLUE)
    box(d,(920,180,1200,360),"ScoreBatch",["record_id / task_name","score","连续数值，可校准"])
    box(d,(920,470,1200,650),"RankBatch",["record_id / group_id","rank","组内排序，供验证/提交"])
    box(d,(1280,250,1530,550),"不可变性守卫",["✓ 只读字符串","✓ 版本化变换","✓ 分组可比性","× 无生成方法","× 无优化方法"],"#FFF7E8",GOLD)
    arrow(d,[(380,270),(490,270)]); arrow(d,[(380,560),(450,560),(450,470),(490,470)])
    arrow(d,[(800,320),(910,320)]); arrow(d,[(800,480),(910,480)]); arrow(d,[(1200,400),(1270,400)])
    d.rounded_rectangle((70,735,1530,815),14,fill=WHITE,outline="#CBD5E1",width=2)
    d.text((100,762),"评价层：真实标签 → 明确 rank 方法 → Spearman；模型选择只看无泄漏折外预测。来源：阶段0接口规划。",font=font(17),fill=MUTED)
    im.save(OUT / "阶段0_排序模型接口图.png")


def competition_architecture():
    im = Image.new("RGB", (1800, 1000), BG); d = ImageDraw.Draw(im)
    d.text((70, 42), "初赛主线与第二阶段预留接口", font=font(40), fill=INK)
    d.text((70, 100), "实线：最大化无泄漏 Spearman；虚线：只预留未来接口，不代表已有模型或结果", font=font(19), fill=MUTED)
    top = [
        ((70, 215, 350, 385), "官方公开数据", ["已有抗原 / 抗体记录", "标签与来源元数据"], WHITE, "#9CB7D9"),
        ((420, 215, 740, 385), "清洗、去重与防泄漏划分", ["抗原 · 家族 · 聚类 · 结构同源", "固定折与折外预测"], PALE, BLUE),
        ((810, 215, 1110, 385), "共享预训练编码器", ["抗原编码 · 抗体编码", "交互融合 · 冻结/部分微调"], PALE, BLUE),
        ((1180, 190, 1530, 410), "Affinity Ranking Head", ["MSE/Huber baseline", "Pairwise · Listwise · Joint loss", "主选模指标：OOF Spearman"], "#FFF7E8", GOLD),
        ((1580, 225, 1750, 375), "候选排名", ["rank ensemble"], PALE, BLUE),
    ]
    for xy, title, lines, fill, stroke in top:
        box(d, xy, title, lines, fill, stroke)
    for a, b in zip(top, top[1:]):
        arrow(d, [(a[0][2], 300), (b[0][0] - 10, 300)])
    d.text((70, 490), "第二阶段接口预留（不占用当前主线训练预算）", font=font(23), fill=INK)
    reserved = [
        ((100, 575, 370, 705), "Binding", "ELISA 阳性概率头"),
        ((430, 575, 700, 705), "Expression", "排序 / 回归头"),
        ((760, 575, 1030, 705), "Aggregation", "风险评分头"),
        ((1090, 575, 1360, 705), "Novelty", "合法性与硬过滤接口"),
        ((1420, 575, 1720, 705), "Portfolio Selection", "6 候选组合与多样性接口"),
    ]
    for xy, title, line in reserved:
        d.rounded_rectangle(xy, 15, fill=WHITE, outline="#7F8DA3", width=2)
        # Dashed top/bottom strokes make the reserved status visible without color.
        for x in range(xy[0] + 10, xy[2] - 10, 20):
            d.line((x, xy[1], min(x + 10, xy[2]), xy[1]), fill="#7F8DA3", width=3)
            d.line((x, xy[3], min(x + 10, xy[2]), xy[3]), fill="#7F8DA3", width=3)
        d.text((xy[0] + 30, xy[1] + 28), title, font=font(22), fill=INK)
        d.text((xy[0] + 30, xy[1] + 74), line, font=font(16), fill=MUTED)
        cx = (xy[0] + xy[2]) // 2
        dashed_line(d, [(960, 470), (cx, 470), (cx, 565)])
    d.rounded_rectangle((70, 810, 1750, 930), 16, fill=WHITE, outline="#CBD5E1", width=2)
    d.text((100, 835), "验证合同", font=font(22), fill=INK)
    d.text((100, 875), "全局 Spearman · macro Spearman（按抗原）· Pearson · RMSE/MAE · Top-k · 来源/类型/区间分组", font=font(17), fill=MUTED)
    d.text((100, 905), "来源：赛事官方全文与 DataCastle 官方页面（2026-07-26）。阶段0仅建立架构，不含训练结果。", font=font(16), fill=MUTED)
    im.save(OUT / "阶段0_初赛主线与复赛预留架构图.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    road_map(); interface_map(); competition_architecture()
