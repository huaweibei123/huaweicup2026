#!/usr/bin/env python3
"""Arithmetic/report enrichment only; no optimization, scoring or simulation."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import json,csv,hashlib,ast,argparse

def dumpcsv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main(root,out):
    p=out/'audit_tables.json';data=json.loads(p.read_text());rows=data['rows']
    for x in rows:
        x['official_curve_point']=1.0 if x['cores']==1 else x['A_cell']
        x['L_conditional_combined']=max(x['L_safe_global'],x['L_conditional_archived'])
        x['C_cell_conditional_combined']=x['B']/x['L_conditional_combined']
        x['old_integer_scalar_certified_by_domination']=x['L_conditional_archived']<=x['L_safe_global']
        x['safe_global_dominant']='separator' if x['L_safe_separator']>x['L_safe_compute_window'] else x['compute_window_dominant']
        x['safe_global_max_makespan_cycles_reduction']=x['U']-x['L_safe_global']
        x['mean_speedup_gap_contribution_cap']=(x['B']/x['L_safe_global']-x['B']/x['U'])/100
    summaries=[];combo=[];extreme=[];counts=[]
    for k in range(1,6):
        rs=[x for x in rows if x['cores']==k];safe=data['summary']['official_integer_global'][k-1];old=data['summary']['conditional_archived'][k-1]
        A=Fraction(1) if k==1 else sum((Fraction(x['B'],x['U']) for x in rs),Fraction())/100
        CC=sum((Fraction(x['B'],x['L_conditional_combined']) for x in rs),Fraction())/100
        combo.append({'cores':k,'A':float(A),'C':float(CC),'C_minus_A':float(CC-A),'relative_mean_gain_cap':float(CC/A-1),'C_fraction':str(CC)})
        summaries.append(dict(cores=k,official_A=safe['A'],L_scope='integer retained-compute window plus universal-separator gates',
            safe_C=safe['C'],safe_C_minus_A=safe['C_minus_A'],safe_relative_mean_gain_cap=safe['relative_mean_gain_cap'],
            conditional_archived_C=old['C'],conditional_combined_C=float(CC),
            mean_of_cell_relative_gain_NOT_mean_score_gain=safe['unweighted_mean_cell_speed_gain'],
            official_plot_anchor=1 if k==1 else '',plot_note='K1 fixed reference only, do not plot its optimization cap as a claimed score' if k==1 else '',
            rows_with_spill=sum(x['spill_bytes']>0 for x in rs),
            old_scalars_certified_by_new_bound=sum(x['old_integer_scalar_certified_by_domination'] for x in rs)))
        if k>1:
            for label,key,rev in [('closest',lambda x:Fraction(x['U'],x['L_safe_global']),False),('widest',lambda x:Fraction(x['U'],x['L_safe_global']),True),('largest_mean_cap_contribution',lambda x:Fraction(x['B'],x['L_safe_global'])-Fraction(x['B'],x['U']),True)]:
                for rank,x in enumerate(sorted(rs,key=key,reverse=rev)[:5],1):
                    extreme.append({a:x[a] for a in ['case_id','cores','B','U','L_safe_global','safe_global_max_makespan_reduction','safe_global_max_relative_speed_gain','safe_global_dominant','spill_bytes','mean_speedup_gap_contribution_cap']}|{'category':label,'rank':rank})
        counts.append({'cores':k,'dominance':dict(Counter(x['safe_global_dominant'] for x in rs))})
    data['summary']['conditional_combined']=combo;data['dominant_components']=counts;data['extremes']=extreme
    data['official_scope_note']='Integer E0 control-flow invariants, conditional only on successful frozen official execution, not ideal DDR service conservation. New author proofs pending external independent audit.'
    data['all_matrix_feasibility_note']='500 feed statuses and identities audited; raw 500 plans/results/traces are absent. No independent execution or raw feasibility rerun is claimed.'
    data['k1_note']='B is fixed official one-Task baseline. Official curve point is 1; U of a repartitioned K1 candidate is stored for audit only.'
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');dumpcsv(out/'paired_500_audited.csv',rows);dumpcsv(out/'summary.csv',summaries);dumpcsv(out/'closest_widest.csv',extreme)
    manifest=json.loads((root/'MANIFEST.json').read_text());focus={'src/q1/lower_bounds.py','src/q1/unified.py','src/q1/capacity_return.py','src/q1/fork_frontier.py','src/q1/bounded_tasks.py','src/q1/structure.py'}
    inventory=[]
    for x in manifest:
        file=root/x['path'];entry=dict(x);entry['hash_verified']=hashlib.sha256(file.read_bytes()).hexdigest()==x['sha256'];entry['length_verified']=file.stat().st_size==x['size_bytes']
        if file.suffix=='.py':
            text=file.read_text();tree=ast.parse(text);entry['functions']=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            entry['reading_scope']='重点正文与关键执行路径审计；未执行' if 'official/code/' in x['path'] or x['path'] in focus or x['path'].startswith('recent/') else '源码文本与函数/导入结构阅读；未逐路径证明、未执行'
        elif file.suffix=='.json':entry['reading_scope']='JSON完整解析；大表按字段逐行算术/身份核对，非原始E0执行复核' if 'feed' in file.name or 'bounds' in x['path'] or 'paired' in file.name or 'reusable' in file.name else 'JSON完整解析与来源/结构核查'
        elif file.suffix=='.zip':entry['reading_scope']='解压并解析全部100张原始JSON；未调用编译或评估'
        elif file.suffix=='.csv':entry['reading_scope']='CSV完整读取并核对JSON派生字段'
        else:entry['reading_scope']='文本正文阅读'
        inventory.append(entry)
    (out/'read_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
    # Independently compare CSV projection with the provided JSON table.
    supplied=list(csv.DictReader((root/'derived/paired-bounds-v4.csv').open(encoding='utf-8-sig')))
    assert len(supplied)==500
    derived=json.loads((root/'derived/paired-bounds-v4.json').read_text())['rows'];idx={(str(x['case_id']).zfill(3),str(x['cores'])):x for x in derived}
    for x in supplied:
        y=idx[x['case_id'].zfill(3),x['cores']]
        for k,v in x.items():
            if k not in y:continue
            if isinstance(y[k],(float,int)) and not isinstance(y[k],bool):assert abs(float(v)-y[k])<=1e-10*max(1,abs(y[k])),(x['case_id'],k)
            else:assert v==str(y[k]),(x['case_id'],k,v,y[k])
    print(json.dumps({'summary':summaries,'provided_csv_matches':500,'inventory':len(inventory)},ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/mnt/data/p1_r4_evidence'));p.add_argument('--out',type=Path,default=Path('/mnt/data/p1_r4_report'));a=p.parse_args();main(a.root,a.out)
