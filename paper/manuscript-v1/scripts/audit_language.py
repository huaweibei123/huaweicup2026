#!/usr/bin/env python3
"""Locate known ambiguous wording; this does not certify prose correctness."""
from pathlib import Path
import hashlib,json,re,subprocess
P=Path(__file__).resolve().parents[1]
R=P/'review'; R.mkdir(exist_ok=True)
BASE='6f30680aaad7cceb83b7d1f7623938ec24d5bc0a'
rules=[
 ('流水(?!线)','缩写省略','必须写全流水线（pipeline）并定义本题资源；若指时间重叠，写清哪些操作同时进行。'),
 ('真实流水|实际流水|流水线就绪关系','未定义的组合表述','区分执行资源、就绪条件和时间重叠；不得暗示硬件实测。'),
 ('生产者|消费者|消费','借喻省略动作','写明生成或读取哪个张量的哪一类操作。'),
 ('物理张量|物理实例|逻辑身份|物理执行','对象不明确','区分原图节点、复制后的数据实例、逻辑标识和官方模拟，不以物理作泛指。'),
 ('费用|计费|代价','量的含义未明确','说明是B、cycle还是s；写出该量包括和排除的部分。'),
 ('触核|触及Core|触及 Core|核序|核链|归核','压缩表达','用集合或函数精确定义涉及的Core，写完整的分配或执行顺序。'),
 ('守卫|工作帽|锚回|赢家|装箱|拖尾|援助|重组件','机制标签代替步骤','撤销不必要命名，说明选择对象、约束、操作及接受条件。'),
 ('前沿|波次|波内|波高度|容量返回|私有返回','未定义结构','先用原图的节点和边说明结构，再给判定条件；无必要的作者名称删除。'),
 ('代理|日历|memory-credit|spill|singleton|fresh incumbent|incumbent|gap|fanout|runtime checkpoint','未解释外语或压缩对象','核对标准原词；给出本文对象及局限，不只补括号或机械翻译。'),
 ('商空间|未来充分|动作词|合法语言|响应表示|执行契约|机制 DAG|语义身份','抽象对象未充分说明','给出集合、操作、条件和例子；删除不服务当前算法的命名。'),
 ('屏障|释放|发射|门控|门槛|指令|请求','条件和动作需核对','明确谁等待谁、何时开始、受什么条件限制，不混用Task开始与操作开始。'),
 ('(Task|Pipe|Cache|FIFO|DDR|DAG|UB|L1|L2|NPU|COPY)','首次定义/范围核对','逐一核对题面原词与本文定义，首次展开完整名称，后续不自造缩写。'),
 ('格|网格|feed|worker|墙钟|证书|身份|收据','研发用语需解释','改为输入图/核数测试组合、结果清单、工作进程或具体可核对对象。'),
 ('主导|结构化|语义一致|闭环|投影|响应|强化窗口|原子','过度名词化需复核','具体说明处理什么对象、采用何种运算和为什么，不把形容词当论据。')]
old=json.loads((R/'checkpoint-01-text.json').read_text())['files']
pdf=P/'checkpoints/checkpoint-01/anonymous-paper-v1.pdf'
pages=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True).split('\f')
flat=lambda x:re.sub(r'\s+','',x)
entries=[]
for file,text in old.items():
 if file.endswith('09-references.md'):continue
 in_plan=False
 for ln,line in enumerate(text.splitlines(),1):
  if line.startswith('::: figure-plan'):in_plan=True
  if line==':::':in_plan=False;continue
  if not line.strip() or line.startswith('<!--'):continue
  hits=[]
  for pattern,kind,issue in rules:
   terms=list(dict.fromkeys(re.findall(pattern,line)))
   if terms:hits.append({'terms':terms,'kind':kind,'requirement':issue})
  if not hits:continue
  clean=re.sub(r'[*`#$]','',line)
  probe=flat(clean[:35])
  page=next((i+1 for i,p in enumerate(pages) if len(probe)>7 and probe in flat(p)),None)
  entries.append({'id':f'LANG-{len(entries)+1:04d}','chapter':file,'line':ln,'original':line,'term':list(dict.fromkeys(t for h in hits for t in h['terms'])),'issue':hits,'replacement':None,'source':['data/raw/a/problem.pdf §§1.1–1.5 and Appendices B–D','review/term-sources.json'],'status':'open','author_status_only':True,'scope':'figure_specification' if in_plan else 'manuscript','pdf_page':page,'english_full':None,'official_chinese':None,'definition':None,'definition_location':None})
out={'schema_version':1,'manuscript_commit':BASE,'paper_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'scope':'checkpoint-01 chapters, abstract, appendix and figure specifications; figure bitmap labels and generated LaTeX captions require separate review','method':'Known-phrase scan plus author paragraph review; matches are review candidates, not proof of error or completeness. No entry is independently accepted.','entries':entries}
(R/'language-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(len(entries),'locations queued for review')
