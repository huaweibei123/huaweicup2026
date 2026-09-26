"""Manim supplement, generated from the same JSON as the paper proof figure.

Example: python -m manim -ql --fps 24 -r 1280,720 --media_dir BUILD_DIR
         paper/manuscript-v1/scripts/manim_frontier.py FrontierExchange
"""
import json
from pathlib import Path
import manimpango
from manim import *

BASE=Path(__file__).resolve().parents[1]
font=BASE.parent/'template-2026'/'fonts'/'SimSun.ttf'
if font.exists(): manimpango.register_font(str(font))
INK='#243244'; BLUE='#416A93'; TEAL='#2D918A'; ORANGE='#C9874D'; GRAY='#A6ADB5'

class FrontierExchange(Scene):
    def construct(self):
        self.camera.background_color=WHITE
        d=json.loads((BASE/'figures'/'fig-forest-frontier.json').read_text())
        def text(s,size=30,color=INK):return Text(s,font='SimSun',font_size=size,color=color)
        def card(name,x,col):
            obj=d[name];r=RoundedRectangle(width=4.7,height=1.45,corner_radius=.1,stroke_color=col,stroke_width=2,fill_color=WHITE,fill_opacity=1)
            t=text(f"{name}   h = {obj['h']}   r = {obj['r']}\nh − r = {obj['h']-obj['r']}",32,col)
            return VGroup(r,t).move_to([x,1.25,0])
        title=text('为什么先处理 h − r 较大的子树？',39).to_edge(UP,buff=.5)
        subtitle=text('非交错局部模型 · KiB · 证明示例，非硬件实测',25).next_to(title,DOWN,buff=.24)
        A=card('A',2.8,BLUE);B=card('B',-2.8,TEAL)
        axis=Line([-5.25,-1.0,0],[5.25,-1.0,0],color=GRAY)
        unit=.55;origin=np.array([-5.0,-.6,0])
        def bars(hold,peak,hold_color,peak_color):
            left=Rectangle(width=hold*unit,height=.55,stroke_width=0,fill_color=hold_color,fill_opacity=1).move_to(origin+np.array([hold*unit/2,0,0]))
            right=Rectangle(width=peak*unit,height=.55,stroke_width=0,fill_color=peak_color,fill_opacity=.55).move_to(origin+np.array([(hold+peak/2)*unit,0,0]))
            return VGroup(left,right)
        bar=bars(d['B']['r'],d['A']['h'],TEAL,BLUE)
        rule=text('先 B 后 A：保留 B 的根，再承受 A 的峰值',30).move_to([0,-1.45,0])
        formula=text('rB + hA = 5 + 8 = 13',35).move_to([0,-2.15,0])
        self.play(FadeIn(title),FadeIn(subtitle));self.play(FadeIn(B),FadeIn(A));self.wait(.5)
        self.play(Create(axis),FadeIn(bar),FadeIn(rule),FadeIn(formula));self.wait(2)
        self.play(A.animate.move_to([-2.8,1.25,0]),B.animate.move_to([2.8,1.25,0]),run_time=1.3)
        newbars=bars(d['A']['r'],d['B']['h'],BLUE,TEAL)
        self.play(Transform(bar,newbars),Transform(rule,text('交换后：保留更小的根，给下一棵树留出空间',30).move_to(rule)),
                  Transform(formula,text('rA + hB = 2 + 7 = 9',35).move_to(formula)),run_time=1.5)
        self.wait(2)
        final=text('父输出先分配：2 + 5 + 3 = 10',33,color=ORANGE).move_to([0,-2.75,0])
        self.play(FadeIn(final));self.wait(1.5)
        conclusion=text('完整局部峰值：13 → 10',37,color=BLUE).move_to([0,-3.35,0])
        self.play(FadeIn(conclusion));self.wait(2)
