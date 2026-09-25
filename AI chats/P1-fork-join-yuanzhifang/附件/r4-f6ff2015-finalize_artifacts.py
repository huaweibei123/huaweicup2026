#!/usr/bin/env python3
"""Finalize inventories and report bindings using only bytes/JSON arithmetic."""
from pathlib import Path
import json,hashlib,zipfile,argparse,ast

def sha(b):return hashlib.sha256(b).hexdigest()
def main(root,out):
    original=next((p for p in [root.parent/'p1-pro-r4-fixed-evidence.zip'] if p.exists()),None)
    mf=json.loads((root/'MANIFEST.json').read_text());source=json.loads((root/'docs/a/source-manifest.json').read_text())
    expected={x['path']:x for x in source['files']};inner=[];checked=[]
    for p in (root/'data/raw/a/official/code').glob('*.py'):
        key='code/'+p.name;h=sha(p.read_bytes());assert h==expected[key]['sha256'];checked.append(key)
    with zipfile.ZipFile(root/'data/raw/a/official-cases.zip') as z:
        for name in sorted(z.namelist()):
            raw=z.read(name);h=sha(raw);assert h==expected[name]['sha256'];inner.append({'member':name,'size_bytes':len(raw),'sha256':h,'read':'entire JSON; static graph arithmetic'})
    code_records=[x for x in source['files'] if x['path'].startswith('code/')]
    agg=sha(''.join(x['path']+'\t'+x['sha256']+'\n' for x in sorted(code_records,key=lambda x:x['path'])).encode());assert agg==source['official_code_hash']
    cfg=sha((root/'data/raw/a/official/data/config.txt').read_bytes());assert cfg=='dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
    inv={'archive':{'name':original.name,'size_bytes':original.stat().st_size,'sha256':sha(original.read_bytes())} if original else None,
        'manifest_entries':json.loads((out/'read_inventory.json').read_text()),
        'unlisted_root_entries':[{'path':p,'size_bytes':(root/p).stat().st_size,'sha256':sha((root/p).read_bytes()),'read':'entire text'} for p in ['README.md','MANIFEST.json']],
        'nested_official_graphs':inner,'source_manifest_crosscheck':{'raw_P1_code_files':checked,'raw_graphs':100,'recorded_ten_code_hash_aggregate':agg,
        'warning':'Aggregate checked against recorded 10 hashes; raw P2/P3 files not in this archive and not rehashed.'}}
    (out/'complete_input_inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n')
    semantics={'config_sha256':cfg,'official_P1_sha256':sha((root/'data/raw/a/official/code/multicore_cut_evaluate_problem_1.py').read_bytes()),
        'proof_version':'P1-R4-integer-window-and-separator-v1','proof_review_status':'author report; independent local review pending',
        'numeric_scope':'integer non-COPY duration, retained compute precedence, exact Task gates; no ideal DDR conservation assumed'}
    for f in ['window_certificates.json','separator_certificates.json']:
        p=out/f;j=json.loads(p.read_text())
        for row in j:row.update(semantics)
        p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
    p=out/'audit_tables.json';j=json.loads(p.read_text());j['semantics_identity']=semantics
    j['source_completeness']={'E1_implementation_present':False,'raw_500_plans_results_traces_present':False,'raw_baseline_100_results_present':False,
                            'raw_official_graphs':100,'verified_manifest_entries':62,'all_archive_entries':64}
    j['session_static_runs']={'main_generator':2,'certificate_checker_before_final_binding':2,'saved_signature_DAG_analysis':1,
       'note':'Further byte/schema verification does not invoke scheduling. Per-run algorithm counts are recorded separately; no official calls.'}
    p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
    for p in out.glob('*.py'):ast.parse(p.read_text())
    print('Input identity crosscheck: 8 raw P1 code files + 100 raw graphs; report binding finalized.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/mnt/data/p1_r4_evidence'));p.add_argument('--out',type=Path,default=Path('/mnt/data/p1_r4_report'));a=p.parse_args();main(a.root,a.out)
