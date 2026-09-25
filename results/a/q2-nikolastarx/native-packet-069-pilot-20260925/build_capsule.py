"""Read committed source and saved evidence; no constructor or evaluator."""
import hashlib, json, subprocess, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sha=lambda data:hashlib.sha256(data).hexdigest()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
files={}
# Reuse only verified frozen raw inputs/official files from the prior capsule.
old=ROOT/'output/rcx-069-k5-colab-20260925-v1/p2-rcx-069-k5-s8ee-20260925.zip'
with zipfile.ZipFile(old) as z:
    manifest=json.loads(z.read('manifest.json'))
    for name in manifest['files']:
        if name.startswith('data/raw/') or name in ('inputs/plan.json.gz','inputs/result.json.gz'):
            data=z.read(name)
            assert sha(data)==manifest['files'][name]
            files[name]=data
with zipfile.ZipFile(ROOT/'output/rcx-069-k5-colab-20260925-v1/results.zip') as z:
    files['inputs/contract.json.gz']=z.read('output/contract.json.gz')
for name in subprocess.check_output(['git','ls-files','src/q2_nikolastarx/*.py'],cwd=ROOT,text=True).splitlines():
    files[name]=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
for name in ('scripts/q2_rcx_fixed_e0_probe.py','scripts/q2_packet_native_pilot.py','scripts/e2_linux_native.py'):
    files[name]=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
with zipfile.ZipFile(ROOT/'output/colab-copyguard-linux-20260925/capsule.zip') as z:
    fixed=z.read('fixed-p2-manifest.json')
    assert sha(fixed)=='9ee379269c0c4f25b64f9d0aeaf1e397e85e48c2103b08637db356d3c9595387'
    files['fixed-p2-manifest.json']=fixed
    sources=json.loads(fixed)['e2_sources']
    assert len(sources)==50
    for name,digest in sources.items():
        data=z.read('e2-src/'+name)
        assert sha(data)==digest
        files['e2-src/'+name]=data
binary=(ROOT/'output/colab-copyguard-linux-20260925/downloaded/linux-native/libreplay_bc.so').read_bytes()
assert sha(binary)=='77ece8929ddcc04e6087dd1c8fc02ee61e79f03b79499182b9f069122092ab3a'
files['e2-src/research/a/e2_search/native/libreplay_bc.so']=binary
receipt=(ROOT/'output/colab-copyguard-linux-20260925/downloaded/e2-linux-build.json').read_bytes()
assert sha(receipt)=='6be18cdf50290a9fd478a468cd421a10fbd25bd10a94e502170dd14fb6a906ef'
files['attestation/e2-linux-build.json']=receipt
limits={'workers':1,'wall_seconds':120,'rss_bytes':536870912,'propose':1,'native_E2':17,'E0':1,'E1':0,'separate_prepare':0,'retries':0}
manifest={'schema':'q2-packet-native-069-k5-v1','source_commit':head,'runner_commit':head,'limits':limits,
    'inputs':{'graph':'data/raw/a/official/data/case_069.json','config':'data/raw/a/official/data/config.txt','plan':'inputs/plan.json.gz','reference_result':'inputs/result.json.gz','contract':'inputs/contract.json.gz'},
    'files':{name:sha(data) for name,data in sorted(files.items())}}
raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
(OUT/'manifest.json').write_bytes(raw)
files['manifest.json']=raw
archive=OUT/'p2-packet-native2-069-k5-s8ee-20260925.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for name,data in sorted(files.items()):
        info=zipfile.ZipInfo(name,(2026,9,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100644<<16
        z.writestr(info,data)
freeze={'capsule_sha256':sha(archive.read_bytes()),'capsule_bytes':archive.stat().st_size,'manifest_sha256':sha(raw),'source_commit':head,'runner_commit':head,'members':len(files),'uncompressed_bytes':sum(map(len,files.values())),'limits':limits}
(OUT/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
print(json.dumps(freeze))
