"""Inventory the editable flowcharts actually inserted in frozen paper v8.

This reads fixed Git objects only. It does not rewrite labels or diagrams.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("inventory.json")

SOURCES = [
    ("fig:p1-complete-flow", "83e03c093af991ec7414f80787984726ebdea329",
     "figures/a/p1-834-flow-20260926/p1-834-flow-clean.drawio"),
    ("fig:p2-local-cut", "4eb1dd426b25bde8871a31835416676314a50519",
     "figures/a/p2-local-cut-v4-20260926/p2-local-cut.drawio"),
    ("fig:p2-three-plans:a", "4eb1dd426b25bde8871a31835416676314a50519",
     "figures/a/p2-three-plans-v4-20260926/a-construction.drawio"),
    ("fig:p2-three-plans:b", "4eb1dd426b25bde8871a31835416676314a50519",
     "figures/a/p2-three-plans-v4-20260926/b-scoring.drawio"),
    ("fig:p3-forest-decision", "4eb1dd426b25bde8871a31835416676314a50519",
     "figures/a/p3-forest-decision-v4-20260926/p3-forest-decision.drawio"),
]


def clean_label(raw: str) -> str:
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()


def main() -> None:
    figures = []
    for figure_id, commit, path in SOURCES:
        xml = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{path}"])
        drawing = ET.fromstring(xml)
        labels = []
        edges = []
        for cell in drawing.iter("mxCell"):
            cell_id = cell.get("id")
            if cell.get("edge") == "1":
                edges.append([cell_id, cell.get("source"), cell.get("target")])
            original = cell.get("value", "")
            if original.strip():
                labels.append({"cell_id": cell_id, "original": clean_label(original)})
        figures.append({
            "figure_id": figure_id,
            "source_commit": commit,
            "source_path": path,
            "source_sha256": hashlib.sha256(xml).hexdigest(),
            "labels": labels,
            "edge_count": len(edges),
            "topology_sha256": hashlib.sha256(json.dumps(edges, ensure_ascii=False,
                                                  separators=(",", ":")).encode()).hexdigest(),
        })
    OUT.write_text(json.dumps({"schema_version": 1, "manuscript": "frozen v8",
                               "purpose": "fixed source and cell IDs for language/caption mapping",
                               "figures": figures}, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(figures)} drawings; {sum(len(f['labels']) for f in figures)} labels -> {OUT}")


if __name__ == "__main__":
    main()
