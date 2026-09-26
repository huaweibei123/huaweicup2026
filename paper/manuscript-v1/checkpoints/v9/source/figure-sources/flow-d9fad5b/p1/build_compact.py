"""Build the shorter P1 flowchart from its byte-identical frozen v8 source."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = "65ca4c43a1ec9dbffaeaa5551ea12304eead954d3e0f60168920dbacd3b77e48"

# The removed cells contain conditions, budgets, and exceptions that must be
# preserved in the accompanying caption. They have no graph connectors.
REMOVE = {"base_note", "response_text", "intact_note", "branch_note"}
RECTS = {
    "paper-background": (52, 0, 856, 1080),
    "input": (52, 25, 856, 55),
    "base": (52, 115, 856, 180),
    "base1": (78, 169, 250, 45), "base2": (355, 169, 250, 45), "base3": (632, 169, 250, 45),
    "base4": (78, 236, 250, 45), "base5": (355, 236, 250, 45), "base6": (632, 236, 250, 45),
    "response": (52, 330, 856, 65),
    "intact": (52, 430, 856, 125),
    "mode1": (95, 485, 318, 50), "mode2": (515, 485, 318, 50),
    "branch": (52, 590, 856, 240),
    "donor": (84, 650, 353, 150), "helper": (532, 650, 345, 150),
    "x": (112, 695, 297, 40), "yj": (112, 748, 297, 43),
    "helper_text": (554, 700, 300, 70),
    "guard": (52, 865, 856, 60),
    "output": (52, 960, 856, 55),
    "e0": (52, 1030, 856, 30),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = HERE / "p1-834-flow-clean.drawio"
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, "source Draw.io changed"
    drawing = ET.fromstring(raw)
    cells = {c.get("id"): c for c in drawing.iter("mxCell")}
    old_edges = [(c.get("id"), c.get("source"), c.get("target"))
                 for c in drawing.iter("mxCell") if c.get("edge") == "1"]
    mapping = json.loads(args.mapping.read_text())
    if not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                            for k, v in mapping.items()):
        raise ValueError("mapping must be an object from cell ID to figure text")
    for cell_id, wording in mapping.items():
        if cell_id not in cells or not cells[cell_id].get("value", "").strip():
            raise ValueError(f"unknown or unlabelled cell: {cell_id}")
        cells[cell_id].set("value", wording)
    for cell_id, rect in RECTS.items():
        geometry = cells[cell_id].find("mxGeometry")
        if geometry is None:
            raise ValueError(f"missing geometry: {cell_id}")
        for key, value in zip(("x", "y", "width", "height"), rect):
            geometry.set(key, str(value))
    for parent in drawing.iter():
        for child in list(parent):
            if child.tag == "mxCell" and child.get("id") in REMOVE:
                parent.remove(child)
    for model in drawing.iter("mxGraphModel"):
        model.set("dy", "1080")
        model.set("pageHeight", "1080")
    new_edges = [(c.get("id"), c.get("source"), c.get("target"))
                 for c in drawing.iter("mxCell") if c.get("edge") == "1"]
    assert old_edges == new_edges, "connector topology changed"
    ET.indent(drawing, space="  ")
    args.output.write_bytes(ET.tostring(drawing, encoding="utf-8", xml_declaration=True))
    print(args.output)


if __name__ == "__main__":
    main()
