"""Move the fixed P2 diagram's explanations into its caption without changing edges."""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = "c1bdbb3adfabeab5fe23f593f9a9c99ac01307f7fa0940e659f08332e51280ea"
REMOVE = {"a_formula", "a_note", "b_formula", "guard_bound"}
LABELS = {
    "scope": "所选核心：a、b；可移动计算链：u、v",
    "a_title": "例 A｜区域外尚未触及其他核心（Fₑ = ∅）",
    "a_cost": "同侧：C = 0；分侧：C = w",
    "b_title": "例 B｜区域外已触及核心 a、c（Fₑ = {a, c}）",
    "b_cost": "全在 a：C = w；有链在 b：C = 2w",
    "guard_title": "局部最小割后检查各核心的计算流水线工作量",
    "guard_cut": "求局部最小割",
    "guard_cap": "若工作量超限，固定该流水线工作量最大的迁入链，再求最小割",
    "guard_accept": "工作量合规且局部复制量不增时，返回局部分配",
}
RECTS = {
    "scope": (52, 18, 856, 62),
    "a_panel": (52, 100, 856, 265),
    "a_title": (76, 117, 808, 42),
    "a_pins1": (92, 182, 166, 51), "a_aux1": (374, 182, 203, 51),
    "a_sink": (694, 182, 166, 51),
    "a_source": (92, 257, 166, 51), "a_aux2": (374, 257, 203, 51),
    "a_pins2": (694, 257, 166, 51),
    "a_cost": (79, 317, 802, 33),
    "b_panel": (52, 385, 856, 200),
    "b_title": (76, 401, 808, 42),
    "b_source": (92, 460, 166, 51), "b_aux": (374, 460, 203, 51),
    "b_pins": (694, 460, 166, 51),
    "b_cost": (79, 536, 802, 33),
    "guard_panel": (52, 605, 856, 220),
    "guard_title": (76, 622, 808, 42),
    "guard_cut": (80, 686, 238, 105),
    "guard_cap": (363, 686, 238, 105),
    "guard_accept": (646, 686, 238, 105),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = (HERE / "p2-local-cut.drawio").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, "source Draw.io changed"
    drawing = ET.fromstring(raw)
    cells = {cell.get("id"): cell for cell in drawing.iter("mxCell")}
    old_edges = [(cell.get("id"), cell.get("source"), cell.get("target"), cell.get("value"))
                 for cell in drawing.iter("mxCell") if cell.get("edge") == "1"]
    assert not any(cell.get("source") in REMOVE or cell.get("target") in REMOVE
                   for cell in drawing.iter("mxCell") if cell.get("edge") == "1")
    for cell_id, label in LABELS.items():
        cells[cell_id].set("value", label)
    for cell_id, (x, y, width, height) in RECTS.items():
        geometry = cells[cell_id].find("mxGeometry")
        for key, value in zip(("x", "y", "width", "height"), (x, y, width, height)):
            geometry.set(key, str(value))
    for parent in drawing.iter():
        for child in list(parent):
            if child.tag == "mxCell" and child.get("id") in REMOVE:
                parent.remove(child)
    for model in drawing.iter("mxGraphModel"):
        model.set("dy", "845")
        model.set("pageHeight", "845")
    new_edges = [(cell.get("id"), cell.get("source"), cell.get("target"), cell.get("value"))
                 for cell in drawing.iter("mxCell") if cell.get("edge") == "1"]
    assert old_edges == new_edges, "edge endpoints or capacities changed"
    ET.indent(drawing, space="  ")
    args.output.write_bytes(ET.tostring(drawing, encoding="utf-8", xml_declaration=True))
    print(args.output)


if __name__ == "__main__":
    main()
