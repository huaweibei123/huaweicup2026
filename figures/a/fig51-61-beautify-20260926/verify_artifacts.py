from pathlib import Path
import csv,json,hashlib
from PIL import Image
import pymupdf
root=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={"5-1":"16e0b22aeb7849fdc986d8bb06548ac1c0a7378173fbaa2f93ae4ecb90b734f4","6-1":"9f134160b9c88c150229a4c3893583960bd2af4e74ea53dd3564d8b5dfaf8b90"}
report={"platform":"Windows","status":"user_confirmed_A_pending_captain_review","figures":[],"new_evaluator_runs":0,"post_confirmation_imagegen_calls":0}
for fig,n,e in [("5-1",17,19),("6-1",12,11)]:
    d=root/f"fig{fig}"; p=d/f"fig{fig}-A-confirmed.png"
    assert sha(p)==expected[fig]
    audit=json.loads((d/"source/audit.json").read_text(encoding="utf-8-sig"))
    for entry in audit["files"]: assert sha(d/"source"/entry["name"])==entry["sha256"],entry["name"]
    nodes=list(csv.DictReader((d/"source/nodes.csv").open(encoding="utf-8-sig",newline="")))
    edges=list(csv.DictReader((d/"source/edges.csv").open(encoding="utf-8-sig",newline="")))
    assert (len(nodes),len(edges))==(n,e)
    ids={x["id"] for x in nodes}
    assert len(ids)==n and all(x["source"] in ids and x["target"] in ids for x in edges)
    with Image.open(p) as im:
        im.load()
        image={"size_px":list(im.size),"mode":im.mode,"sha256":sha(p),"bytes":p.stat().st_size,"alpha":list(im.getchannel("A").getextrema()),"ppi_at_147mm":im.width*25.4/147}
    pdf=pymupdf.open(d/"page-preview.pdf")
    assert len(pdf)==1
    page=pdf[0]; text=page.get_text()
    assert "\uffff" not in text and "\ufffd" not in text
    assert f"图 {fig.replace('-','.')}" in text or f"图{fig.replace('-','.')}" in text,text
    pics=page.get_image_info()
    assert len(pics)==1
    bbox=pics[0]["bbox"]
    w=(bbox[2]-bbox[0])*25.4/72; h=(bbox[3]-bbox[1])*25.4/72
    assert abs(w-147)<0.02 and abs(h-220.5)<0.02
    assert page.rect.contains(pymupdf.Rect(bbox))
    text_boxes=[b["bbox"] for b in page.get_text("dict")["blocks"] if b["type"]==0]
    assert all(page.rect.contains(pymupdf.Rect(x)) for x in text_boxes)
    report["figures"].append({"id":fig,"source_files_verified":len(audit["files"]),"nodes":n,"edges":e,"image":image,"pdf":{"pages":1,"page_mm":[round(v*25.4/72,2) for v in (page.rect.width,page.rect.height)],"image_width_mm":w,"image_height_mm":h,"image_bbox_pt":bbox,"caption_text":text.strip(),"sha256":sha(d/"page-preview.pdf")}})
report["metadata_residue"]=[p.relative_to(root).as_posix() for p in root.rglob("*") if p.name.startswith("._") or p.name in (".DS_Store","__MACOSX")]
assert not report["metadata_residue"]
(root/"verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
files=[{"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(root.rglob("*")) if p.is_file() and p.name!="manifest.json"]
(root/"manifest.json").write_text(json.dumps(files,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
