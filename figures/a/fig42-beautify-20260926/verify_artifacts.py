import csv, hashlib, json
from pathlib import Path
from graphlib import TopologicalSorter
from PIL import Image
root=Path(__file__).resolve().parent
expected={
'fig4-2-A-confirmed.png':'76b1b13c073f404dc7c51e60f7ceecbcd51aaeb5cc9fdc3ea775614061592b3f',
'source/fig4-2-fork-join-partition.drawio':'e85877755cc61fcceaf219dee5f5761d19201d2cde4590c774fc259efef2ea56',
'source/nodes.csv':'5616588b8dbc96afbdf1e249d10169a4d371dbc57ba889cddc6d2799781690b1',
'source/edges.csv':'047a1e2ab66ad5c3c453b581278ca44be8db2dfdec05fe7d4fa092132aa3f574'}
for name,h in expected.items(): assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name
nodes=list(csv.DictReader((root/'source/nodes.csv').open(encoding='utf-8-sig')))
edges=list(csv.DictReader((root/'source/edges.csv').open(encoding='utf-8-sig')))
ids={n['id'] for n in nodes}
assert len(ids)==len(nodes)==12 and len(edges)==13
es={(e['source'],e['target']) for e in edges}
assert es=={('s','a'),('a','b1'),('a','b2'),('a','b3'),('b1','c1'),('c1','d1'),('b2','d2'),('b3','c3'),('c3','d3'),('d1','r'),('d2','r'),('d3','r'),('r','t')}
deps={n:set() for n in ids}
for a,b in es: deps[b].add(a)
assert len(list(TopologicalSorter(deps).static_order()))==12
node_tasks={n['id']:n['subgraph'] for n in nodes}
td={(node_tasks[a],node_tasks[b]) for a,b in es if node_tasks[a]!=node_tasks[b]}
assert td=={('task0','task1'),('task0','task2'),('task0','task3'),('task1','task4'),('task2','task4'),('task3','task4')}
schedules={1:['task0','task1'],2:['task2','task4'],3:['task3']}
for n in nodes: assert schedules[int(n['core'])][int(n['order'])-1]==n['subgraph']
taskdep={t:set() for t in set(node_tasks.values())}
for a,b in td: taskdep[b].add(a)
for order in schedules.values():
 for a,b in zip(order,order[1:]): taskdep[b].add(a)
assert len(list(TopologicalSorter(taskdep).static_order()))==5
im=Image.open(root/'fig4-2-A-confirmed.png')
assert im.size==(1536,1024) and im.mode=='RGBA'
hist=im.getchannel('A').histogram()
bad=[p.name for p in root.rglob('*') if p.name.startswith('._') or p.name in ('.DS_Store','__MACOSX')]
assert not bad,bad
out={'status':'user_confirmed_pending_captain_review','confirmation':'就用A这一版比较好','source_commit':'0a710ab1a0fcebe313c3a78d877d9c698cc27ec0','style_commit':'6de5103496a40a6067ff837dcabd9e797118ef35','language_commit':'5313ff6ab3241bb81465b3b761e97ab12700d8fe','language_version':'2026-09-26.6','image':{'size':im.size,'mode':im.mode,'alpha_extrema':im.getchannel('A').getextrema(),'transparent_pixels':hist[0],'ppi_at_165mm':round(im.width*25.4/165,2)},'checks':{'nodes':12,'edges':13,'tasks':5,'task_dependencies':6,'acyclic':True,'source_and_confirmed_hashes_match':True,'apple_metadata_files':bad},'files':{}}
for p in sorted(root.rglob('*')):
 if p.is_file() and p.name!='manifest.json': out['files'][p.relative_to(root).as_posix()]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(root/'manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'image':out['image'],'checks':out['checks'],'files':len(out['files'])},ensure_ascii=False))
