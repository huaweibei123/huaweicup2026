#!/usr/bin/env python3
"""Flag sparse PDF pages for editorial review; not a substitute for reading.

The body bounds follow template-2026: top 30 mm; bottom including footer 26.5 mm.
Only trailing whitespace is measured. No claim about aesthetic quality or correctness.
"""
from pathlib import Path
import argparse,json,subprocess
import numpy as np
from PIL import Image,ImageDraw

a=argparse.ArgumentParser();a.add_argument('pdf',type=Path);a.add_argument('output',type=Path);args=a.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
subprocess.run(['pdftoppm','-scale-to','1000','-png',str(args.pdf),str(args.output/'page')],check=True)
files=sorted(args.output.glob('page-*.png'));records=[]
for i,f in enumerate(files,1):
 im=np.asarray(Image.open(f).convert('L')); h,w=im.shape
 y0,y1=round(h*30/297),round(h*(297-26.5)/297)
 x0,x1=round(w*22.5/210),round(w*(210-22.5)/210)
 body=im[y0:y1,x0:x1];ink=np.count_nonzero(body<200,axis=1)>=3
 occupied=np.flatnonzero(ink);last=int(occupied[-1]+1) if len(occupied) else 0
 gap=(len(ink)-last)/len(ink)
 records.append({'page':i,'trailing_blank_fraction':round(gap,4),'ink_row_fraction':round(float(ink.mean()),4),'review':gap>.25})
for start in range(0,len(files),9):
 sheet=Image.new('RGB',(1200,1710),'#e3e5e7');d=ImageDraw.Draw(sheet)
 for j,f in enumerate(files[start:start+9]):
  im=Image.open(f).convert('RGB');im.thumbnail((390,540));x=j%3*400+(400-im.width)//2;y=j//3*570+24
  sheet.paste(im,(x,y));r=records[start+j]
  d.text((j%3*400+10,j//3*570+5),f"p{r['page']} tail {r['trailing_blank_fraction']:.0%}",fill='black')
 sheet.save(args.output/f'overview-{start//9+1}.jpg')
report={'pdf':str(args.pdf),'page_count':len(records),'scope':'trailing empty fraction of template text body, excluding footer; flags require visual review','pages':records}
(args.output/'density.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pages':len(records),'flagged':[r for r in records if r['review']]},ensure_ascii=False))
