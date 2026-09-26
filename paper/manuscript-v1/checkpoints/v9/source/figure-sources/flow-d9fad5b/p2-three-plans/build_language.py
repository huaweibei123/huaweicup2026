"""Shorten fixed P2 figure labels; detailed conditions stay in source-caption.md."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = {
    "a-construction": "7d9b352f7b3e095e739c7e36b585ab213c6240ee581d75382f89b318d1751654",
    "b-scoring": "5077a89afa03f9cf117fd505bc8e3838f2065ef2891d263ac7c3dd98242e9fac",
}
LABELS = {
    "a-construction": {
        "p0": "P0：基础方案\n始终保留",
        "keep": "保留原始 P1\n与 P0 相同则不重复列入",
        "gate": "全图重排前复制字节数\n是否严格减少？",
        "skip": "不构造 P2\n保留已有方案",
        "fallback": "出错则返回 P0",
    },
    "b-scoring": {
        "dedup": "删除相同的完整方案\n顺序：P0 → P1 → P2",
        "score": "逐份评分\n最多调用 3 次",
        "choose": "先比较总完成时间\n相同再比较\n额外 COPY 字节数",
        "tie": "指标相同：保留先构造的方案",
    },
}


def main() -> None:
    for name, source_sha256 in SOURCES.items():
        raw = (HERE / f"{name}.drawio").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source_sha256, f"source changed: {name}"
        drawing = ET.fromstring(raw)
        cells = {cell.get("id"): cell for cell in drawing.iter("mxCell")}
        old_edges = [(cell.get("id"), cell.get("source"), cell.get("target"),
                      ET.tostring(cell.find("mxGeometry")))
                     for cell in drawing.iter("mxCell") if cell.get("edge") == "1"]
        for cell_id, label in LABELS[name].items():
            cells[cell_id].set("value", label)
        new_edges = [(cell.get("id"), cell.get("source"), cell.get("target"),
                      ET.tostring(cell.find("mxGeometry")))
                     for cell in drawing.iter("mxCell") if cell.get("edge") == "1"]
        assert old_edges == new_edges, "control flow changed"
        ET.indent(drawing, space="  ")
        output = HERE / f"{name}-language.drawio"
        output.write_bytes(ET.tostring(drawing, encoding="utf-8", xml_declaration=True))
        print(output)


if __name__ == "__main__":
    main()
