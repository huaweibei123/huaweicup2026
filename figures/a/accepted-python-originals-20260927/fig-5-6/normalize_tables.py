"""Normalize verified certificate scope labels and coalesce equal ECDF abscissae.
No changes to U/L values or plotted probability distribution. No experiments.
"""
import csv
from pathlib import Path
p=Path(__file__).resolve().parent
def read(n):return list(csv.DictReader((p/n).open(encoding='utf-8')))
def write(n,rs):
 with (p/n).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]),lineterminator='\n');w.writeheader();w.writerows(rs)
rows=read('bounds.csv')
for r in rows:
 assert r['domain']=='at most one eligible producer per original tensor'
 r['applicability']=r['domain'];r['domain']='global'
write('bounds-normalized.csv',rows)
out=[]
for k in range(1,6):
 vals=sorted(float(r['gap']) for r in rows if int(r['cores'])==k)
 for x in sorted(set(vals)):out.append(dict(cores=k,gap=x,cdf=sum(v<=x for v in vals)/len(vals)))
write('ecdf-normalized.csv',out)
