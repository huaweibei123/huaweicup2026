#!/usr/bin/env python3
"""Build two editable Draw.io panels for the fixed P2 three-plan route."""
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
INK = '#17324D'
BLUE = ('#E9F2F8', '#447EAA')
TEAL = ('#E4F4EF', '#378B75')
AMBER = ('#FFF3DC', '#BA842C')
RED = ('#FCEBE9', '#BC615B')
GRAY = ('#F5F8FA', '#93A9BA')


class Panel:
    def __init__(self, name, width, height):
        self.root = ET.Element('mxfile', host='app.diagrams.net', version='30.0.2', type='device')
        diagram = ET.SubElement(self.root, 'diagram', id=name, name=name)
        model = ET.SubElement(diagram, 'mxGraphModel', dx=str(width), dy=str(height), grid='1', gridSize='10', page='1', pageWidth=str(width), pageHeight=str(height), math='0', shadow='0')
        self.cells = ET.SubElement(model, 'root')
        ET.SubElement(self.cells, 'mxCell', id='0')
        ET.SubElement(self.cells, 'mxCell', id='1', parent='0')

    def box(self, key, value, x, y, w, h, color=BLUE, size=27):
        fill, stroke = color
        style = (f'rounded=1;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};'
                 f'strokeWidth=2;fontColor={INK};fontFamily=PingFang SC;fontSize={size};'
                 'fontStyle=1;align=center;verticalAlign=middle;spacing=8;')
        cell = ET.SubElement(self.cells, 'mxCell', id=key, value=value, style=style, vertex='1', parent='1')
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as': 'geometry'})

    def text(self, key, value, x, y, w, h, size=22, color=INK):
        style = (f'text;html=0;fillColor=none;strokeColor=none;fontColor={color};'
                 f'fontFamily=PingFang SC;fontSize={size};fontStyle=1;'
                 'align=center;verticalAlign=middle;whiteSpace=wrap;')
        cell = ET.SubElement(self.cells, 'mxCell', id=key, value=value, style=style, vertex='1', parent='1')
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as': 'geometry'})

    def arrow(self, key, route, color='#657F91', dashed=False):
        style = (f'edgeStyle=none;html=0;strokeColor={color};strokeWidth=2.7;'
                 f'endArrow=block;endFill=1;dashed={int(dashed)};')
        cell = ET.SubElement(self.cells, 'mxCell', id=key, style=style, edge='1', parent='1')
        geo = ET.SubElement(cell, 'mxGeometry', relative='1', attrib={'as': 'geometry'})
        ET.SubElement(geo, 'mxPoint', x=str(route[0][0]), y=str(route[0][1]), attrib={'as': 'sourcePoint'})
        ET.SubElement(geo, 'mxPoint', x=str(route[-1][0]), y=str(route[-1][1]), attrib={'as': 'targetPoint'})
        arr = ET.SubElement(geo, 'Array', attrib={'as': 'points'})
        for x, y in route[1:-1]:
            ET.SubElement(arr, 'mxPoint', x=str(x), y=str(y))

    def write(self, filename):
        ET.indent(self.root, space='  ')
        path = HERE / filename
        path.write_bytes(ET.tostring(self.root, encoding='utf-8', xml_declaration=True))
        print(path)


# (a) Constructor. The red rail represents immediate returns; the gray rail
# represents a supported skip that keeps already constructed complete plans.
a = Panel('a-construction', 1200, 780)
a.text('pa', '(a) 构造候选完整方案', 30, 12, 1140, 42, 29)
a.box('p0', 'P0：基础方案\n始终保留', 45, 90, 290, 105, BLUE)
a.box('p1', '尝试构造 P1', 450, 90, 290, 105, TEAL)
a.box('keep', '保留原始 P1\n相同则不重复入列', 855, 90, 290, 105, TEAL, 25)
a.box('refine', '以原始 P1\n尝试局部调整', 855, 260, 290, 105, AMBER)
a.box('gate', '原始 COPY 字节数\n有效且严格下降？', 855, 430, 290, 105, AMBER, 25)
a.box('p2', '尝试重排\n成功则生成完整 P2', 855, 610, 290, 105, AMBER)
a.box('fallback', '立即返回 P0', 45, 400, 290, 100, RED)
a.box('skip', '不构造 P2\n保留已有方案', 450, 610, 290, 105, GRAY)
a.arrow('a01', [(335,142),(450,142)])
a.arrow('a12', [(740,142),(855,142)])
a.arrow('a23', [(1000,195),(1000,260)])
a.arrow('a34', [(1000,365),(1000,430)])
a.arrow('a45', [(1000,535),(1000,610)], '#A17C3B')
a.arrow('a_p1err', [(450,180),(392,180),(392,445),(335,445)], '#B45D57')
a.arrow('a_err', [(855,317),(785,317),(785,555),(390,555),(390,485),(335,485)], '#B45D57')
a.arrow('a_no', [(855,500),(820,500),(820,662),(740,662)], '#A17C3B')
a.arrow('a_retime_skip', [(855,686),(740,686)], '#A17C3B', True)
a.arrow('a_retime_error', [(1000,715),(1000,750),(25,750),(25,485),(45,485)], '#B45D57')
a.text('lerr1', '失败', 299, 222, 70, 35, 23, '#A1453E')
a.text('lerr2', '错误／无效证据', 538, 510, 220, 34, 23, '#A1453E')
a.text('lno', '不支持／否', 682, 570, 125, 35, 23, '#94702D')
a.text('lyes', '是', 1030, 553, 55, 35, 23, '#94702D')
a.text('lretime', '不支持', 750, 633, 95, 30, 23, '#94702D')
a.text('lretime_error', '错误', 1050, 718, 75, 30, 23, '#A1453E')
a.write('a-construction.drawio')

# (b) Scores only distinct complete plans. All arrows mean control flow.
b = Panel('b-scoring', 1200, 455)
b.text('pb', '(b) 去重、评分与选择', 30, 12, 1140, 42, 29)
b.box('dedup', '完整方案去重\nP0 → P1 → P2', 45, 115, 300, 110, BLUE)
b.box('score', '逐份评分\n总请求 ≤ 3', 450, 115, 300, 110, BLUE)
b.box('choose', '先比较总完成时间\n相同再比较\n额外 COPY 字节数', 855, 115, 300, 110, TEAL, 23)
b.box('only', '仅一份：直接返回 P0', 45, 320, 300, 85, GRAY, 25)
b.box('error', '评分错误：返回 P0', 450, 320, 300, 85, RED, 25)
b.box('tie', '平局：保留先构造者', 855, 320, 300, 85, TEAL, 25)
b.arrow('b01', [(345,170),(450,170)])
b.arrow('b12', [(750,170),(855,170)])
b.arrow('b_only', [(195,225),(195,320)])
b.arrow('b_error', [(600,225),(600,320)], '#B45D57')
b.arrow('b_tie', [(1005,225),(1005,320)])
b.text('b_many', '≥ 2 份', 357, 122, 87, 35, 23)
b.text('b_one', '= 1 份', 209, 247, 93, 35, 23)
b.write('b-scoring.drawio')
