#!/usr/bin/env python3
"""Build an editable, text-sparing two-panel diagram for the fixed P3 policy."""
from pathlib import Path
from xml.etree import ElementTree as ET

OUT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1000, 860
COLORS = {
    "ink": "#183246", "muted": "#50697A", "line": "#68879A",
    "blue": "#EAF3F8", "teal": "#E7F4EF", "amber": "#FFF2DD",
    "gray": "#F2F5F6", "white": "#FFFFFF", "red": "#B54E48",
}

doc = ET.Element("mxfile", host="app.diagrams.net", agent="deterministic-python",
                 version="30.0.2", type="device")
diagram = ET.SubElement(doc, "diagram", id="p3-forest-v4", name="树状排序与官方评价")
model = ET.SubElement(diagram, "mxGraphModel", dx=str(WIDTH), dy=str(HEIGHT),
                      grid="0", page="1", pageScale="1", pageWidth=str(WIDTH),
                      pageHeight=str(HEIGHT), math="0", shadow="0")
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")


def box(name, text, x, y, w, h, *, fill="white", stroke="line",
        size=24, bold=False, align="center"):
    style = ("rounded=1;arcSize=10;whiteSpace=wrap;html=1;"
             f"fillColor={COLORS[fill]};strokeColor={COLORS[stroke]};strokeWidth=1.6;"
             f"fontColor={COLORS['ink']};fontFamily=PingFang SC;fontSize={size};"
             f"fontStyle={int(bold)};align={align};verticalAlign=middle;"
             "spacingLeft=14;spacingRight=14;spacingTop=9;spacingBottom=9;")
    node = ET.SubElement(root, "mxCell", id=name, value=text, style=style,
                         vertex="1", parent="1")
    ET.SubElement(node, "mxGeometry", x=str(x), y=str(y), width=str(w),
                  height=str(h), attrib={"as": "geometry"})


def label(name, text, x, y, w, h, size=25, color="ink"):
    style = ("text;html=1;whiteSpace=wrap;fillColor=none;strokeColor=none;"
             f"fontColor={COLORS[color]};fontFamily=PingFang SC;fontSize={size};"
             "fontStyle=1;align=left;verticalAlign=middle;")
    node = ET.SubElement(root, "mxCell", id=name, value=text, style=style,
                         vertex="1", parent="1")
    ET.SubElement(node, "mxGeometry", x=str(x), y=str(y), width=str(w),
                  height=str(h), attrib={"as": "geometry"})


def arrow(name, source, target, *, exit_x=1, exit_y=.5, entry_x=0, entry_y=.5):
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
             f"html=1;strokeColor={COLORS['line']};strokeWidth=2.2;"
             "endArrow=block;endFill=1;"
             f"exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;"
             f"entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;")
    node = ET.SubElement(root, "mxCell", id=name, style=style, edge="1",
                         source=source, target=target, parent="1")
    ET.SubElement(node, "mxGeometry", relative="1", attrib={"as": "geometry"})


def routed_arrow(name, points, *, color="line", arrowhead=True):
    style = ("edgeStyle=none;html=1;rounded=0;"
             f"strokeColor={COLORS[color]};strokeWidth=2.2;"
             f"endArrow={'block' if arrowhead else 'none'};endFill=1;")
    node = ET.SubElement(root, "mxCell", id=name, style=style, edge="1", parent="1")
    geo = ET.SubElement(node, "mxGeometry", relative="1", attrib={"as": "geometry"})
    ET.SubElement(geo, "mxPoint", x=str(points[0][0]), y=str(points[0][1]),
                  attrib={"as": "sourcePoint"})
    ET.SubElement(geo, "mxPoint", x=str(points[-1][0]), y=str(points[-1][1]),
                  attrib={"as": "targetPoint"})
    middle = ET.SubElement(geo, "Array", attrib={"as": "points"})
    for x, y in points[1:-1]:
        ET.SubElement(middle, "mxPoint", x=str(x), y=str(y))


# The whole-figure title and scientific caveats belong to caption.md.
label("a", "(a) 归约树内部结果的排序", 40, 16, 920, 43)
box("scope", "适用：至少两棵互不交错的归约树，且存在汇合；<br>单输出且字节数已知；非根输出仅供唯一父操作。",
    40, 78, 280, 214, fill="blue", size=22)
box("order", "同一父操作的各子树：<br>计算 hᵢ − rᵢ，按差值递减；<br>同值按操作编号排序。",
    360, 78, 280, 214, fill="teal", size=23)
box("guarantee", "只保证此非交错树模型内，每棵树内部结果的峰值占用最小。",
    680, 78, 280, 214, fill="amber", size=24)
arrow("a1", "scope", "order")
arrow("a2", "order", "guarantee")

label("b", "(b) 树状排序方案与其他方案共用官方评价预算", 40, 332, 920, 43)
box("prior", "基础方案与先行方案已产生当前最优方案", 80, 390, 610, 58,
    fill="blue", size=23, bold=True)

# Vertical main route. Every rejection has a horizontal exit to one shared
# terminal rail; no failed gate appears to continue to the next stage.
box("budget", "① 官方评价器 E0 已调用次数 < 3？",
    80, 480, 610, 70, fill="gray", size=24)
box("structure", "② 树状方案通过构造与本地检查？",
    80, 575, 610, 70, fill="gray", size=24)
box("distinct", "③ 序列化字节表示与当前最优方案不同？",
    80, 670, 610, 70, fill="gray", size=23)
box("bound", "④ 若可得下界：是否 ≥ 当前最优完成时间？<br>下界不可得时继续评价。",
    80, 765, 610, 70, fill="amber", size=22)
box("e0", "⑤ 在剩余预算内调用官方 E0；结果有效？",
    80, 860, 610, 70, fill="teal", size=24)
box("select", "⑥ 官方完成时间严格更短？",
    80, 955, 610, 70, fill="blue", size=24)
box("replace", "替换当前最优方案", 80, 1060, 610, 70,
    fill="teal", size=24, bold=True)
box("retain", "保留当前最优方案", 730, 1060, 230, 70,
    fill="gray", size=21, bold=True)

for name, source, target in [
    ("b0", "prior", "budget"), ("b1", "budget", "structure"),
    ("b2", "structure", "distinct"), ("b3", "distinct", "bound"),
    ("b4", "bound", "e0"), ("b5", "e0", "select"),
    ("b6", "select", "replace"),
]:
    arrow(name, source, target, exit_x=.5, exit_y=1, entry_x=.5, entry_y=0)

# A shared right-hand termination rail expresses the source-code early returns.
for name, y in [
    ("fail_budget", 515), ("fail_structure", 610),
    ("fail_distinct", 705), ("fail_bound", 800),
    ("fail_e0", 895), ("fail_select", 990),
]:
    routed_arrow(name, [(690, y), (845, y)], color="red", arrowhead=False)
routed_arrow("retained", [(845, 515), (845, 1060)], color="red")
for name, text, y in [
    ("no_budget", "否", 492), ("no_structure", "否", 587),
    ("no_distinct", "否", 682), ("no_bound", "下界排除", 777),
    ("no_e0", "无效", 872), ("no_select", "否", 967),
]:
    label(name, text, 710, y - 14, 123, 31, size=20, color="red")

ET.indent(doc, space="  ")
(OUT / "p3-forest-decision.drawio").write_bytes(
    ET.tostring(doc, encoding="utf-8", xml_declaration=True))
print(OUT / "p3-forest-decision.drawio")
