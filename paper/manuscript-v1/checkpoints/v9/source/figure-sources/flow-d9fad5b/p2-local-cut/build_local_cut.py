"""Build the editable, source-audited P2 local-cut explanation.

The symbolic hyperedges are didactic examples, not contest measurements.
No solver or evaluator is imported or run.
"""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
SOLVER_COMMIT = "c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f"
W, H = 960, 1130

nodes = [
    ("scope", "所选两个核心：a、b；至多 16 条可移动计算链\nFₑ：同一超边在调整区域外已固定触及的核心集合", 52, 22, 856, 94, "scope"),
    ("a_panel", "", 52, 139, 856, 358, "panel"),
    ("a_title", "例 A｜Fₑ = ∅，超边连接两条可移动链 u、v，权重为 w 字节", 76, 157, 808, 43, "heading"),
    ("a_formula", "复制字节数 C = w ×（触及核心数 − 1）；源侧代表核心 a，汇侧代表核心 b。", 78, 205, 804, 38, "formula"),
    ("a_pins1", "u、v", 92, 273, 166, 51, "pin"),
    ("a_aux1", "辅助节点 q_a", 374, 273, 203, 51, "aux"),
    ("a_sink", "汇侧：b", 694, 273, 166, 51, "side"),
    ("a_source", "源侧：a", 92, 351, 166, 51, "side"),
    ("a_aux2", "辅助节点 q_b", 374, 351, 203, 51, "aux"),
    ("a_pins2", "u、v", 694, 351, 166, 51, "pin"),
    ("a_note", "两行的 u、v 是同一组链；分别列出“有链在 a”和“有链在 b”的容量边。", 86, 416, 788, 29, "note"),
    ("a_cost", "同侧：割容量 w，偏移 −w，C = 0。     分侧：割容量 2w，偏移 −w，C = w。", 79, 452, 802, 32, "result"),
    ("b_panel", "", 52, 515, 856, 275, "panel"),
    ("b_title", "例 B｜Fₑ = {a, c}：已固定触及所选核心 a 和另一个核心 c", 76, 535, 808, 43, "heading"),
    ("b_formula", "a 已在 Fₑ 中，不再建立“有链在 a”的容量边；只有新增核心 b 才增加复制。", 78, 588, 804, 37, "formula"),
    ("b_source", "源侧：a", 92, 648, 166, 51, "side"),
    ("b_aux", "辅助节点 q_b", 374, 648, 203, 51, "aux"),
    ("b_pins", "u、v", 694, 648, 166, 51, "pin"),
    ("b_cost", "全部在 a：割容量 0，偏移 +w，C = w。   有链在 b：割容量 w，偏移 +w，C = 2w。", 79, 733, 802, 37, "result"),
    ("guard_panel", "", 52, 808, 856, 285, "panel"),
    ("guard_title", "局部最小割之后，检查计算工作量（模拟时钟周期）", 76, 828, 808, 44, "heading"),
    ("guard_cut", "求最小割\n精确比较当前区域的\n原始 COPY 字节数", 80, 895, 238, 108, "step"),
    ("guard_cap", "逐核、逐类检查\n计算流水线（Pipe）工作量\n超限：移入链回原核\n并重求最小割", 363, 895, 238, 108, "step_small"),
    ("guard_accept", "只在工作量满足上限、\n局部复制字节数严格减少时\n保留新的核心分配", 646, 895, 238, 108, "step"),
    ("guard_bound", "若有 r 条可移动链，最多求解 r + 1 次；原分配始终可行。", 91, 1038, 778, 39, "result"),
]

edges = [
    ("a_or_a_inf", "a_pins1", "a_aux1", "∞"),
    ("a_or_a_w", "a_aux1", "a_sink", "w"),
    ("a_or_b_w", "a_source", "a_aux2", "w"),
    ("a_or_b_inf", "a_aux2", "a_pins2", "∞"),
    ("b_or_b_w", "b_source", "b_aux", "w"),
    ("b_or_b_inf", "b_aux", "b_pins", "∞"),
    ("guard_1", "guard_cut", "guard_cap", ""),
    ("guard_2", "guard_cap", "guard_accept", ""),
]

palette = {
    "scope": ("#EAF2F9", "#254D71", "#173042", 21, 1),
    "panel": ("#FFFFFF", "#314B62", "#173042", 20, 0),
    "heading": ("#FFFFFF", "#FFFFFF", "#173042", 24, 1),
    "formula": ("#FFFFFF", "#FFFFFF", "#314B62", 20, 0),
    "pin": ("#E7F5F2", "#268078", "#173042", 21, 1),
    "aux": ("#F1EBFA", "#795A9D", "#173042", 21, 1),
    "side": ("#EAF2F9", "#315F84", "#173042", 21, 1),
    "note": ("#FFFFFF", "#FFFFFF", "#40566A", 18, 0),
    "result": ("#F4F8ED", "#A4BF8A", "#284531", 19, 1),
    "step": ("#F7FBFE", "#4E7898", "#173042", 20, 1),
    "step_small": ("#F7FBFE", "#4E7898", "#173042", 17, 1),
}


def style(role: str) -> str:
    fill, stroke, ink, font, bold = palette[role]
    border = 0 if role in {"heading", "formula", "note"} else 1.5
    rounded = 1 if role not in {"heading", "formula", "note"} else 0
    return (f"rounded={rounded};whiteSpace=wrap;html=0;fillColor={fill};"
            f"strokeColor={stroke};strokeWidth={border};fontColor={ink};"
            f"fontFamily=PingFang SC;fontSize={font};fontStyle={bold};"
            "align=center;verticalAlign=middle;spacingLeft=12;spacingRight=12;"
            "shadow=0;glass=0;rotatable=0;")


diagram = ET.Element("mxfile", {"host": "app.diagrams.net", "modified": "2026-09-26T00:00:00.000Z",
                                "agent": "Codex", "version": "30.0.2", "type": "device"})
page = ET.SubElement(diagram, "diagram", {"id": "p2-local-cut", "name": "P2 two-core local cut"})
model = ET.SubElement(page, "mxGraphModel", {"dx": str(W), "dy": str(H), "grid": "0",
                                             "guides": "1", "connect": "1", "arrows": "1", "fold": "1",
                                             "page": "1", "pageScale": "1", "pageWidth": str(W),
                                             "pageHeight": str(H), "background": "#FFFFFF",
                                             "math": "0", "shadow": "0"})
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", {"id": "0"})
ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
for ident, label, x, y, width, height, role in nodes:
    cell = ET.SubElement(root, "mxCell", {"id": ident, "value": label,
                                          "style": style(role), "vertex": "1", "parent": "1"})
    ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(width),
                                       "height": str(height), "as": "geometry"})
for ident, source, target, label in edges:
    cell = ET.SubElement(root, "mxCell", {"id": ident, "value": label,
                                          "style": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;strokeColor=#55758B;strokeWidth=2.5;endArrow=block;endFill=1;fontColor=#173042;fontFamily=Arial;fontSize=20;fontStyle=1;labelBackgroundColor=#FFFFFF;",
                                          "edge": "1", "parent": "1", "source": source, "target": target})
    ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

ET.indent(diagram, space="  ")
ET.ElementTree(diagram).write(OUT / "p2-local-cut.drawio", encoding="utf-8", xml_declaration=True)
semantic = {
    "fixed_solver_commit": SOLVER_COMMIT,
    "didactic_example": True,
    "symbols": {"a": "chosen source-side core", "b": "chosen sink-side core", "c": "another fixed core",
                "F_e": "set of cores already touched by pins outside the local region; distinct from scalar maximum-flow value f_max", "w": "positive hyperedge weight in bytes",
                "u,v": "the same two movable chain pins repeated in both auxiliary-edge rows"},
    "nodes": [{"id": n[0], "label": n[1], "role": n[6]} for n in nodes],
    "edges": [{"id": e[0], "source": e[1], "target": e[2], "label": e[3]} for e in edges],
    "source_refs": ["src/q2_nikolastarx/binary_hypercut.py:43-72",
                    "src/q2_nikolastarx/binary_hypercut.py:144-195",
                    "src/q2_nikolastarx/binary_hypercut.py:198-258",
                    "src/q2_nikolastarx/gap_hyperrefine.py:88-142"],
    "verification": {"empty_F_e": {"offset": "-w", "same_side_cost": "0", "split_cost": "w"},
                     "F_e_contains_a_and_c": {"offset": "+w", "all_a_cost": "w", "any_b_cost": "2w"}},
}
(OUT / "semantics.json").write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
