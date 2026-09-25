"""Freeze source and three existing official-result pairs; no construction/evaluation."""
import gzip,hashlib,json,subprocess,zipfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
RAW=Path(os.environ['P2_RAW_DATA_ROOT']).resolve()
sha=lambda b:hashlib.sha256(b).hexdigest()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
files={}
with zipfile.ZipFile(ROOT/'output/packet-native-069-k5-20260925-v2/p2-packet-native2-069-k5-s8ee-20260925.zip') as z:
    prior=json.loads(z.read('manifest.json'))
    for n,h in prior['files'].items():
        if n.startswith(('e2-src/','attestation/','data/raw/a/official/code/')) or n in ('fixed-p2-manifest.json','data/raw/a/official/data/config.txt'):
            b=z.read(n);assert sha(b)==h;files[n]=b
for n in subprocess.check_output(['git','ls-files','src/q2_nikolastarx/*.py'],cwd=ROOT,text=True).splitlines():
    files[n]=subprocess.check_output(['git','show',head+':'+n],cwd=ROOT)
for n in ('scripts/q2_rcx_fixed_e0_probe.py','scripts/q2_packet_native_pilot.py','scripts/q2_shifted_packet_pilot.py','scripts/e2_linux_native.py'):
    files[n]=subprocess.check_output(['git','show',head+':'+n],cwd=ROOT)
archive_root=ROOT/'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
rows=[]; provenance=[]
for c in ('005','069','071'):
    matches=list(archive_root.glob('cases-*/'+c+'-k5'));assert len(matches)==1;folder=matches[0]
    run=json.loads((folder/'run.json').read_bytes());cell=json.loads((folder/'cell.json').read_bytes())
    assert sha((folder/'cell.json').read_bytes())==run['archived_evidence']['cell_receipt']['sha256']
    assert cell['status']=='accepted' and cell['case']==c and cell['cores']==5
    graph=(RAW/('case_'+c+'.json')).read_bytes()
    plan=(folder/'plan.json.gz').read_bytes();result=(folder/'result.json.gz').read_bytes()
    assert sha(graph)==cell['graph_sha256']
    assert sha(gzip.decompress(plan))==cell['plan_sha256']
    assert sha(gzip.decompress(result))==cell['official']['result_sha256']
    row={'case':c,'cores':5,'graph':f'inputs/{c}/graph.json','plan':f'inputs/{c}/plan.json.gz','reference_result':f'inputs/{c}/result.json.gz','sha256':{'graph':sha(graph),'plan':sha(gzip.decompress(plan)),'reference_result':sha(gzip.decompress(result))}}
    rows.append(row)
    for k,b in [('graph',graph),('plan',plan),('reference_result',result)]:files[row[k]]=b
    provenance.append({'case':c,'archive':str(folder.relative_to(ROOT)),'run_sha256':sha((folder/'run.json').read_bytes()),'cell_sha256':sha((folder/'cell.json').read_bytes()),'old_M':cell['official']['makespan'],'old_added_DDR':cell['official']['movement']['added_copy_bytes']})
limits={'workers':1,'wall_seconds':120,'rss_bytes':536870912,'propose':3,'native_E2':27,'E0':3,'E1':0,'separate_prepare':0,'retries':0}
manifest={'schema':'q2-shifted-packet-three-v1','source_commit':head,'runner_commit':head,'limits':limits,'config':'data/raw/a/official/data/config.txt','rows':rows,'files':{n:sha(b) for n,b in sorted(files.items())}}
raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode();(OUT/'manifest.json').write_bytes(raw);files['manifest.json']=raw
archive=OUT/'p2-shifted-three-s8ee-20260925.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for n,b in sorted(files.items()):
        i=zipfile.ZipInfo(n,(2026,9,25,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,b)
freeze={'capsule_sha256':sha(archive.read_bytes()),'capsule_bytes':archive.stat().st_size,'manifest_sha256':sha(raw),'source_commit':head,'runner_commit':head,'members':len(files),'uncompressed_bytes':sum(map(len,files.values())),'limits':limits}
(OUT/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n');(OUT/'input-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(json.dumps(freeze))
