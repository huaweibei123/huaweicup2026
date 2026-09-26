#!/usr/bin/env python3
"""SUPERSEDED prototype: manually reconstructed layout, rejected by visual review.

Geometry is an explicit pixel coordinate system. Scientific objects come from
the frozen stage-1 JSON. This is a localized vector reconstruction, not a claim
of bit-for-bit pixel identity with the model-generated reference.
"""
import json
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Polygon
from matplotlib.path import Path as MPath
from figure_style import PAPER,plt,save
from draw_figures import source

INK='#14213D';GRAY='#546176';EDGE='#A3B2C3';PURPLE='#D9CCF5';PV='#57457C'
BLUE='#337FCC';TEAL='#199E98';AMBER='#D5882E'
PALE={'blue':'#F0F6FF','teal':'#F0FAF8','amber':'#FFF7EB','gray':'#F5F7FA','violet':'#F5F0FC'}
HEAD={'blue':'#E2EFFF','teal':'#DEF4EF','amber':'#FFEBCB','gray':'#EBEFF5','violet':'#EBE2FA'}
COL={'blue':BLUE,'teal':TEAL,'amber':AMBER,'gray':EDGE,'violet':'#8A65BD'}

class Canvas:
    def __init__(self,height=1024):
        self.w=1536;self.h=height;self.fig=plt.figure(figsize=(6.5,6.5*height/1536))
        self.ax=self.fig.add_axes([0,0,1,1]);self.ax.set(xlim=(0,1536),ylim=(height,0));self.ax.axis('off')
    def text(self,x,y,s,size=12,ha='center',bold=False,color=INK):
        return self.ax.text(x,y,s,fontsize=size,ha=ha,va='center',color=color,fontweight='bold' if bold else 'normal',linespacing=1.25,zorder=5)
    def box(self,x,y,w,h,kind='gray',header=None,headheight=58,dash=False):
        patch=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=12',fc=PALE[kind],ec=COL[kind],linewidth=.65,linestyle=(0,(5,4)) if dash else '-',zorder=1)
        self.ax.add_patch(patch)
        if header is not None:
            band=FancyBboxPatch((x+1,y+1),w-2,headheight,boxstyle='round,pad=0,rounding_size=10',fc=HEAD[kind],ec='none',zorder=2)
            self.ax.add_patch(band);self.text(x+w/2,y+headheight/2,header,bold=True)
        return patch
    def node(self,x,y,label,w=112,h=70):
        self.ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0,rounding_size=14',fc=PURPLE,ec=PV,lw=.65,zorder=4))
        self.text(x,y,label,size=11.5,bold=True)
    def line(self,start,end,color=GRAY,arrow=True,dash=False,control=None,width=.8):
        kw=dict(arrowstyle='-|>' if arrow else '-',mutation_scale=9,linewidth=width,color=color,linestyle=(0,(5,3)) if dash else '-',zorder=3)
        if control:
            path=MPath([start,*control,end],[MPath.MOVETO,MPath.CURVE4,MPath.CURVE4,MPath.CURVE4]);p=FancyArrowPatch(path=path,**kw)
        else:p=FancyArrowPatch(start,end,shrinkA=0,shrinkB=0,**kw)
        self.ax.add_patch(p)
    def dot(self,x,y,r=5,color=GRAY):self.ax.add_patch(Circle((x,y),r,fc=color,ec='none',zorder=4))
    def rule(self,y):self.line((30,y),(1506,y),color=EDGE,arrow=False,width=.5)
    def finish(self,name):
        # A physical 165.1-mm canvas ensures Chinese annotations are 12 pt.
        save(self.fig,name,outdir=PAPER/'design'/'rejected-manual-reconstruction')

def partition():
    d=source('p1-026-k5');c=Canvas();coords={710:(135,190),712:(292,190),714:(450,190),716:(609,190),720:(213,342),722:(529,342),724:(370,529),726:(370,670)}
    edges=[(710,720),(712,720),(714,722),(716,722),(720,724),(722,724),(724,726)]
    c.box(36,46,678,729,'gray',header='sg0 · Core 0')
    c.box(812,46,318,356,'blue',header='X · sg0 · Core 0')
    c.box(1140,46,360,356,'teal',header='Y · sg6 · Core 1')
    c.box(812,416,688,359,'amber')
    c.text(840,443,'J · sg5 · Core 0',ha='left')
    for key,shift in [('old',0),('new',780)]:
        pos={i:(x+shift,y) for i,(x,y) in coords.items()}
        for u,v in edges:
            x,y=pos[u];xx,yy=pos[v];cut=key=='new' and d[key]['plan']['node_to_subgraph'][str(u)]!=d[key]['plan']['node_to_subgraph'][str(v)]
            c.line((x,y+35),(xx,yy-39),AMBER if cut else GRAY,dash=cut,
                   control=[(x,y+80),(xx,yy-85)] if x!=xx else None)
        for i,(x,y) in pos.items():c.node(x,y,str(i),w=130 if i in (724,726) else 112)
        for i in (710,712,714,716):
            x,y=pos[i];c.dot(x,109);c.line((x,121),(x,y-40),dash=True)
        c.line((370+shift,710),(370+shift,738),dash=True);c.dot(370+shift,755)
        c.dot(659+shift,670);c.line((646+shift,670),(440+shift,670),dash=True)
        c.text(598+shift,641,'t719 · 2 B',size=10.5)
    c.text(1085,469,'t721 · 2 B',size=10.5);c.text(1338,445,'t723 · 2 B',size=10.5)
    c.line((735,409),(790,409),color=EDGE,width=2)
    c.text(375,817,'(a) 原始划分',bold=True);c.text(1155,817,'(b) 分叉援助细化',bold=True)
    c.rule(867)
    entries=[(163,'case_026','5 核'),(414,'Task','5 → 7'),(708,'Makespan / cycle','44,114 → 42,014'),(1043,'降幅','4.76%'),(1354,'额外 COPY / B','+163,852')]
    for x,title,val in entries:
        c.text(x,898,title,size=12 if any('\u4e00'<=ch<='\u9fff' for ch in title) else 9.5)
        c.text(x,937,val,size=12 if '核' in val else 10.5)
    for x in (304,530,886,1190):c.line((x,891),(x,951),color=EDGE,arrow=False,width=.4)
    c.line((175,992),(260,992));c.text(315,992,'依赖')
    c.line((445,992),(535,992),color=AMBER,dash=True);c.text(620,992,'跨子图')
    c.line((780,992),(830,992),arrow=False,dash=True);c.dot(833,992);c.text(930,992,'图外端口')
    c.node(1090,992,'',w=54,h=36);c.text(1280,992,'ADD 节点编号',size=12)
    c.finish('fig-p1-cuts-final')

def coherent():
    c=Canvas(1152);c.box(443,16,650,66,'gray',header='原图 JSON · 核数 K · 固定配置',headheight=64)
    xs=[30,529,1028];heads=['P1 · Task 屏障','P2 · 核内复用','P3 · 只读 Cache'];kinds=['blue','violet','teal']
    mods=[('组件／波次','分叉援助'),('空隙插入','张量超图'),('结构构造','归约森林')]
    guard=['秩与增广 DAG','带锚点的局部割','h − r 与候选下界']
    for j,(x,h,k) in enumerate(zip(xs,heads,kinds)):
        c.line((768,82),(x+240,151),color=COL[k]);c.box(x,152,478,454,k,header=h,headheight=68)
        for ii in range(2):
            xx=x+20+ii*231;c.box(xx,237,215,270,k);c.text(xx+107,271,mods[j][ii])
            X=xx+107
            if (j,ii)==(1,0):
                for n in range(3):c.line((xx+30+n*54,333),(xx+30+n*54,479),dash=True,arrow=False,width=.4)
                for n in range(3):c.node(xx+70+n*40,369+n*32,'',w=76,h=22)
            elif (j,ii)==(1,1):
                pts=[(X,339),(X-70,385),(X+70,385),(X-51,460),(X+51,460)]
                for p in pts:c.line(p,(X,405),arrow=False,width=.7)
                c.node(X,405,'',w=54,h=35)
                for p in pts:c.ax.add_patch(Circle(p,13,fc=PURPLE,ec=PV,lw=.6,zorder=4))
            else:
                pts=[(X,344),(X-50,406),(X+50,406),(X,468)]
                ed=[(0,1),(0,2),(1,3),(2,3)]
                if (j,ii)==(0,0):ed=[(1,0),(2,0),(0,3)]
                if (j,ii)==(2,1):ed=[(3,1),(1,0),(2,0)]
                for u,v in ed:
                    p=pts[u];q=pts[v];delta=(q[0]-p[0],q[1]-p[1]);norm=(delta[0]**2+delta[1]**2)**.5
                    s=(p[0]+delta[0]*17/norm,p[1]+delta[1]*17/norm);e=(q[0]-delta[0]*19/norm,q[1]-delta[1]*19/norm)
                    c.line(s,e,width=.7)
                for p in pts:c.ax.add_patch(Circle(p,16,fc=PURPLE,ec=PV,lw=.6,zorder=4))
        c.box(x+24,529,430,53,k,dash=True);c.text(x+239,556,guard[j]);c.line((x+239,606),(768,664),COL[k])
    c.box(334,665,868,77,'amber');c.text(768,704,'完整计划 P =（切分，分核，核序）')
    for y,title,kind in [(772,'合法性与适用的必要下界','gray'),(869,'完整执行语义评价','gray'),(965,'保留最佳已确认方案','blue')]:
        c.box(460,y,615,67,kind);c.text(768,y+33,title);c.line((768,y-27),(768,y-4))
    c.rule(1065);c.text(391,1110,'结构提出候选，执行证据决定接受');c.text(1152,1110,'代理 ≠ 证书 ≠ 实测结果')
    c.finish('fig-coherent-final')

def hypercut():
    c=Canvas();centers=[151,394,575]
    c.box(35,79,643,657,'gray');c.box(50,94,246,470,'blue',header='Core 0',headheight=73);c.box(309,94,355,470,'teal',header='Core 1',headheight=73)
    c.box(859,79,642,657,'gray');c.box(874,94,612,470,'blue',header='Core 0',headheight=73)
    for shift in (0,820):
        for x,label in zip(centers,['$u$','$v_1$','$v_2$']):
            c.line((x+shift,282),(357+shift,443),AMBER,arrow=False,control=[(x+shift,376),(357+shift,382)],width=1)
            c.node(x+shift,245,label,w=120,h=77)
        c.ax.add_patch(Circle((357+shift,443),23,fc='#FFD583',ec=AMBER,lw=.8,zorder=4))
        c.box(257+shift,471,201,68,'amber');c.text(350+shift,505,'张量 t')
        c.box(183+shift,582,351,135,'amber');c.text(357+shift,620,r'$\lambda_t = '+('2' if shift==0 else '1')+'$',size=14)
        c.text(357+shift,676,r'$w_t(\lambda_t-1) = '+('w_t' if shift==0 else '0')+'$',size=14)
    c.text(766,308,'联合迁移');c.line((712,383),(824,383),EDGE,width=2)
    c.text(357,788,'(a) 触及两个Core');c.text(1177,788,'(b) 消费者联合迁移')
    c.rule(853);c.text(594,905,'换入换出前的 COPY 字节：',ha='right');c.text(985,905,r'$C+\sum_t w_t(\lambda_t-1)$',size=14)
    c.text(768,970,'连线表示超边关联；字节模型不等于 Makespan 模型。')
    c.finish('fig-hypercut-final')

def progression():
    c=Canvas(1080);xs=[27,547,1004];ws=[510,445,507];heads=['P1 · Task 屏障','P2 · 核内复用','P3 · 只读 Cache'];ks=['blue','violet','teal']
    for j,(x,w,h,k) in enumerate(zip(xs,ws,heads,ks)):
        c.box(x,56,w,440,k,header=h,headheight=70)
        left=x+112;right=x+w-103
        if j==0:
            c.box(x+20,142,218,147,'blue',header='sg0 · Core 0',headheight=48,dash=True)
            c.box(x+w-222,142,205,147,'blue',header='sg5 · Core 0',headheight=48,dash=True)
        else:c.box(x+17,142,w-34,184,k,header='合并 Task · Core 0',headheight=48,dash=True)
        c.node(left,242,'720',w=129,h=63);c.node(right,242,'724',w=129,h=63)
        if j==0:
            for xx,s,wi in [(left,'COPY_OUT',137),(x+w/2,'DDR',120),(right,'COPY_IN',137)]:c.node(xx,347,s,w=wi,h=49)
            c.line((left,277),(left,320));c.line((left+70,347),(x+w/2-64,347));c.line((x+w/2+64,347),(right-72,347));c.line((right,320),(right,278))
            c.text(x+w/2,396,'t721 · 2 B',size=10.5)
        else:
            c.line((left+68,242),(right-68,242));c.text((left+right)/2,215,'t721 · 2 B',size=10.5)
        c.text(x+w/2,458,['独立 Task：产生边界 COPY','同核数据可驻留','沿用 P2，新增共享 Cache'][j])
    c.line((1320,497),(1180,538),TEAL,control=[(1320,535),(1180,508)])
    c.box(28,548,1480,310,'teal',header='P3 · COPY_IN 的 Cache 服务',headheight=63)
    c.node(467,722,'COPY_IN',w=184,h=77)
    c.ax.add_patch(Polygon([[607,722],[677,659],[747,722],[677,785]],fc='#E6F1FF',ec=BLUE,lw=.7,zorder=2));c.text(677,722,'命中？')
    c.line((562,722),(603,722));c.line((725,679),(829,670),control=[(760,660),(795,670)])
    c.line((725,765),(829,790),control=[(760,790),(795,790)])
    c.text(787,645,'是');c.text(787,811,'否')
    c.box(834,627,224,78,'teal');c.text(946,654,'Cache',size=11.5);c.text(946,686,'250 B/cycle',size=10.5)
    c.box(834,751,224,79,'gray');c.text(946,778,'DDR',size=11.5);c.text(946,810,'60 B/cycle',size=10.5)
    c.line((1058,790),(1150,790),dash=True);c.text(1324,790,'完成后填充')
    c.rule(901);c.text(768,956,'同一图与分核方式，逐问改变执行语义。')
    c.text(768,1020,'驻留仍受容量约束；Cache 命中仍保留依赖与跨核同步。')
    c.finish('fig-progression-final')

def main():
    partition();coherent();hypercut();progression()
    out=PAPER/'design'/'localization-review.json'
    out.write_text(json.dumps(dict(method='Code reconstruction of approved generated style, with Chinese explanatory labels',
        units='Explicit 1536-pixel geometry; 6.5 inch canvas; Chinese 12 pt',
        language='Chinese explanations; code identifiers, Task/Cache/Pipe/DDR and mathematics unchanged',
        scope='REJECTED manual reconstruction; not a final figure; do not use in paper.',
        source='Frozen figure-inputs, partition-story.json and approved generated PNGs'),ensure_ascii=False,indent=2)+'\n')
    print('Four localized vector reconstructions rendered.')

if __name__=='__main__':main()
