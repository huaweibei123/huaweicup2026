"""Apply reviewed text to the frozen v8 P3 editable source and shorten its page height.

Run build.py first to reproduce the pinned source drawing. Text changes come
from a separate reviewed JSON object keyed by the original Draw.io cell IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = "391ce699cf7493e90034891cc58727bd5630f5d90b86a0ff23b57e162da88ad7"


def edges(root: ET.Element) -> list[tuple[str | None, str | None, str | None]]:
    return [(c.get("id"), c.get("source"), c.get("target"))
            for c in root.iter("mxCell") if c.get("edge") == "1"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = HERE / "p3-forest-decision.drawio"
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, "source Draw.io changed"
    document = ET.fromstring(raw)
    original_edges = edges(document)
    mapping = json.loads(args.mapping.read_text())
    if not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                            for k, v in mapping.items()):
        raise ValueError("mapping must be an object from cell ID to figure text")
    cells = {c.get("id"): c for c in document.iter("mxCell")}
    for cell_id, wording in mapping.items():
        if cell_id not in cells or not cells[cell_id].get("value", "").strip():
            raise ValueError(f"unknown or unlabelled cell: {cell_id}")
        cells[cell_id].set("value", wording.replace("\n", "<br>"))

    # The figure is tall chiefly because long explanatory sentences occupy
    # three large top boxes and six vertically spaced decision boxes. The
    # reviewed short labels permit a uniform 25% height reduction without
    # shrinking the print font or changing any graph connector endpoint.
    for element in document.iter():
        if element.tag in {"mxGeometry", "mxPoint"}:
            if "y" in element.attrib:
                element.set("y", str(round(float(element.get("y")) * 0.75, 2)))
            if element.tag == "mxGeometry" and "height" in element.attrib:
                element.set("height", str(round(float(element.get("height")) * 0.75, 2)))
    for model in document.iter("mxGraphModel"):
        model.set("pageHeight", "860")

    assert edges(document) == original_edges, "connector topology changed"
    ET.indent(document, space="  ")
    args.output.write_bytes(ET.tostring(document, encoding="utf-8", xml_declaration=True))
    print(args.output)


if __name__ == "__main__":
    main()
