"""Deterministically build the editable P1 flow from source-audited labels.

No solver or evaluator is imported or executed. Run from this directory.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
SHA = "834d8c957538ee069c66aadac9509552a4cc69d7"
W, H = 960, 1420
CLEAN = sys.argv[1:] == ["--clean"]
if sys.argv[1:] not in ([], ["--clean"]):
    raise SystemExit("usage: python3 build_flow.py [--clean]")
STEM = "p1-834-flow-clean" if CLEAN else "p1-834-flow"

# Each source pointer is a line in the fixed Git blob, not the current checkout.
nodes = [
    dict(id="input", label="输入：原始计算图、核数（1～5）及固定硬件配置", x=52, y=32, w=856, h=62,
         role="input", refs=["unified.py:3-4", "unified.py:44-46"]),
    dict(id="base", label="01  根据计算图结构生成基础方案", x=52, y=130, w=856, h=236,
         role="stage", refs=["unified.py:44-153", "unified.py:156-209"]),
    dict(id="base1", label="仅把过大的独立计算部分\n切成较小任务", x=78, y=200, w=250, h=54, role="candidate", refs=["unified.py:18", "unified.py:77", "bounded_tasks.py:1-6"]),
    dict(id="base2", label="把主导计算部分按\n独立输出区域分段", x=355, y=200, w=250, h=54, role="candidate", refs=["unified.py:19-20", "unified.py:95-107", "heavy_suffix.py:1-7", "sink_peel.py:1-8"]),
    dict(id="base3", label="拆分超过各核合理\n工作份额的部分", x=632, y=200, w=250, h=54, role="candidate", refs=["unified.py:21", "unified.py:108-112", "component_overload.py:1-6"]),
    dict(id="base4", label="按共享输入选择用核数；\n或按分叉分配子树¹", x=78, y=272, w=250, h=54, role="candidate", refs=["unified.py:113-128", "shared_input_budget.py:1-6", "fork_frontier.py:1-8"]),
    dict(id="base5", label="在符合条件的计算链上\n调整末段切分点¹", x=355, y=272, w=250, h=54, role="candidate", refs=["unified.py:129-139", "capacity_return.py:1-6"]),
    dict(id="base6", label="按分叉阶段把独立子树\n分配到多个核¹", x=632, y=272, w=250, h=54, role="candidate", refs=["unified.py:140-150", "fork_frontier.py:1-8"]),
    dict(id="base_note", label="¹ 按结构尝试；重复不评分；可选构造或评分失败回退；E1 最多调用 6 次。", x=75, y=334, w=810, h=24,
         role="note", refs=["unified.py:63-74", "unified.py:149-165", "unified.py:187-199"]),
    dict(id="response", label="02  对符合条件的有序计算链重新分组", x=52, y=408, w=856, h=155,
         role="stage", refs=["response_refine.py:134-169", "response_refine.py:170-219", "variable_packet.py:185-286"]),
    dict(id="response_text", label="仅当上一阶段选中经评分的链切分方案时，\n构造至多一份完整新方案；E1 最多调用一次。\n不适用、重复或失败时保留原方案。", x=80, y=464, w=800, h=83,
         role="detail", refs=["response_refine.py:44-58", "response_refine.py:145-169", "response_refine.py:170-219"]),
    dict(id="intact", label="03  尝试两种独立计算链的局部执行顺序", x=52, y=605, w=856, h=155,
         role="stage", refs=["structural_refine.py:20", "structural_refine.py:58-89", "structural_refine.py:107-161"]),
    dict(id="mode1", label="均衡分配计算链；\n汇合计算另列", x=95, y=676, w=318, h=51, role="candidate", refs=["structural_refine.py:20", "intact_frontier.py:102-126", "intact_frontier.py:138-140"]),
    dict(id="mode2", label="主核多留计算链；\n合并可执行的汇合计算", x=515, y=676, w=318, h=51, role="candidate", refs=["structural_refine.py:20", "intact_frontier.py:108-140"]),
    dict(id="intact_note", label="先检查结构、去除重复；E1 最多调用 2 次；失败时保留已选方案。", x=81, y=735, w=800, h=22,
         role="note", refs=["structural_refine.py:77-89", "structural_refine.py:107-161"]),
    dict(id="branch", label="04  按依赖层批量移动可独立执行的计算分支", x=52, y=801, w=856, h=355,
         role="stage", refs=["branch_refine.py:51-59", "branch_aid.py:316-483"]),
    dict(id="donor", label="同一依赖层的原计算任务\n（移出方）", x=84, y=879, w=353, h=220,
         role="donor", refs=["branch_aid.py:359-399", "branch_aid.py:424-430"]),
    dict(id="x", label="X：移出的整条计算分支", x=112, y=950, w=297, h=48,
         role="x", refs=["branch_aid.py:214-241", "branch_aid.py:425-429"]),
    dict(id="yj", label="Y：其余计算；J：汇合后计算\n都留在原核", x=112, y=1021, w=297, h=56,
         role="yj", refs=["branch_aid.py:216-240", "branch_aid.py:425-458"]),
    dict(id="helper", label="同一层已有独立计算任务\n（接收方）", x=532, y=879, w=345, h=220,
         role="helper", refs=["branch_aid.py:386-391", "branch_aid.py:404-417"]),
    dict(id="helper_text", label="多个 X 各成新任务\n先排 X，再排原任务\n本层不兼任移出方", x=554, y=948, w=300, h=96,
         role="detail", refs=["branch_aid.py:386-391", "branch_aid.py:404-417"]),
    dict(id="branch_note", label="每个原任务最多移出一支；批量形成一份完整方案；E1 最多调用一次。", x=82, y=1112, w=804, h=28,
         role="note", refs=["branch_aid.py:393-439", "branch_aid.py:440-480", "branch_refine.py:90-139"]),
    dict(id="guard", label="先比较完工时间（周期）；只有相同时才比较计划 COPY 搬运量（字节）。\n新方案在这一顺序下严格更优，才替换原方案。", x=52, y=1198, w=856, h=77,
         role="guard", refs=["unified.py:175-180", "response_refine.py:40-41", "response_refine.py:203-219", "structural_refine.py:147-159", "branch_refine.py:33-39", "branch_refine.py:133-146"]),
    dict(id="output", label="输出任务划分与各核执行顺序｜在线 E1 总调用上限：10 次（6＋1＋2＋1）", x=52, y=1314, w=856, h=58,
         role="output", refs=["branch_refine.py:149-162", "unified.py:200-209", "branch_refine.py:175-184"]),
    dict(id="e0", label=("官方 E0 独立复评，不进入在线选优" if CLEAN else "候选图｜待科学与语言审核；官方 E0 独立复评，不进入在线选优"), x=52, y=1387, w=856, h=30,
         role="external", refs=["unified.py:208", "response_refine.py:163", "structural_refine.py:76", "branch_refine.py:63"]),
]

edges = [
    dict(id="e_input_base", source="input", target="base", meaning="当前输入进入基础候选构造"),
    dict(id="e_base_response", source="base", target="response", meaning="基础选中方案进入受限链分组；不适用则原样传递"),
    dict(id="e_response_intact", source="response", target="intact", meaning="链分组后选中或回退方案进入两种顺序"),
    dict(id="e_intact_branch", source="intact", target="branch", meaning="局部顺序后选中或回退方案进入 branch_aid"),
    dict(id="e_x_helper", source="x", target="helper_text", meaning="多个 donor 的 X 可批量转入已有 helper Task L 所在核"),
    dict(id="e_branch_guard", source="branch", target="guard", meaning="各阶段有效候选按统一目标严格比较"),
    dict(id="e_guard_output", source="guard", target="output", meaning="输出已选合法计划"),
    dict(id="e_output_e0", source="output", target="e0", meaning="输出计划供闭环外独立 E0 复评", kind="dashed"),
]

palette = {
    "input": ("#EAF2F9", "#254D71"), "stage": ("#FFFFFF", "#314B62"),
    "candidate": ("#E8F4F5", "#26777C"), "note": ("#FFFFFF", "#FFFFFF"),
    "detail": ("#FFFFFF", "#FFFFFF"), "donor": ("#FFF5E7", "#B46F25"),
    "x": ("#FCEAD2", "#A65F18"), "yj": ("#FFF9EF", "#B46F25"),
    "helper": ("#EAF2F9", "#2D668A"), "guard": ("#E9F3EB", "#3B7754"),
    "output": ("#254D71", "#254D71"), "external": ("#F8FAFC", "#F8FAFC"),
}

def vertex_style(n):
    role = n["role"]
    fill, stroke = palette[role]
    font_color = "#FFFFFF" if role == "output" else "#173042"
    size = 21 if role in {"input", "output", "guard"} else 19
    if role in {"note", "external"}:
        size = 19
        font_color = "#40566A"
    if role == "stage":
        size = 23
        font_color = "#173042"
    align = "left" if role in {"stage", "donor", "helper"} else "center"
    vertical = "top" if role in {"stage", "donor", "helper"} else "middle"
    inset = 18 if role == "stage" else 12
    rounded = 1 if role not in {"note", "detail", "external"} else 0
    return (f"rounded={rounded};whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};"
            f"strokeWidth={2 if role in {'stage','guard','output'} else 1.5};fontColor={font_color};"
            f"fontFamily=PingFang SC;fontSize={size};fontStyle={1 if role in {'stage','input','guard','output'} else 0};"
            f"align={align};verticalAlign={vertical};spacingLeft={inset};spacingRight=12;"
            "shadow=0;glass=0;rotatable=0;")

diagram = ET.Element("mxfile", {"host": "app.diagrams.net", "modified": "2026-09-26T00:00:00.000Z",
                                "agent": "Codex", "version": "30.0.2", "type": "device"})
page = ET.SubElement(diagram, "diagram", {"id": "p1-834-flow", "name": "P1 fixed-834 flow candidate"})
model = ET.SubElement(page, "mxGraphModel", {"dx": "960", "dy": "1420", "grid": "0", "gridSize": "10",
                                             "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
                                             "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(W),
                                             "pageHeight": str(H), "math": "0", "shadow": "0",
                                             "background": "#F8FAFC"})
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", {"id": "0"})
ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
back = ET.SubElement(root, "mxCell", {"id": "paper-background", "value": "",
                                       "style": "fillColor=#F8FAFC;strokeColor=none;movable=0;connectable=0;",
                                       "vertex": "1", "parent": "1"})
ET.SubElement(back, "mxGeometry", {"x": "52", "y": "0", "width": "856",
                                    "height": str(H), "as": "geometry"})
for n in nodes:
    cell = ET.SubElement(root, "mxCell", {"id": n["id"], "value": n["label"],
                                          "style": vertex_style(n), "vertex": "1", "parent": "1"})
    ET.SubElement(cell, "mxGeometry", {"x": str(n["x"]), "y": str(n["y"]),
                                       "width": str(n["w"]), "height": str(n["h"]), "as": "geometry"})
for e in edges:
    dashed = "dashed=1;dashPattern=6 4;" if e.get("kind") == "dashed" else ""
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
             "html=0;strokeColor=#55758B;strokeWidth=2;endArrow=block;endFill=1;" + dashed)
    cell = ET.SubElement(root, "mxCell", {"id": e["id"], "value": "", "style": style,
                                          "edge": "1", "parent": "1", "source": e["source"], "target": e["target"]})
    ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

ET.indent(diagram, space="  ")
ET.ElementTree(diagram).write(OUT / f"{STEM}.drawio", encoding="utf-8", xml_declaration=True)
semantic = {"fixed_solver_commit": SHA,
            "source_line_convention": "git show <fixed_solver_commit>:src/q1/<file> | nl -ba",
            "nodes": nodes, "edges": edges,
            "budget": {"base_max_e1": 6, "chain_packet_max_e1": 1,
                       "intact_order_max_e1": 2, "branch_aid_max_e1": 1,
                       "total_max_e1": 10,
                       "interpretation": "upper bounds on online score attempts; actual worker count may be unknown after dispatch failure"}}
(OUT / ("semantics-clean.json" if CLEAN else "semantics.json")).write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
