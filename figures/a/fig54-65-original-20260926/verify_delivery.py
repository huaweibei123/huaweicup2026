"""Read-only byte-identity check against accepted reviews and original audits."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = []
for fig in ("fig-5-4", "fig-6-5"):
    receipt = json.loads((root / (fig + "-accepted-receipt.json")).read_text(encoding="utf-8"))
    review = receipt["review"]
    assert review["decision"] == "approved"
    assert review["submission_id"] == receipt["submission"]["id"]
    for name, digest in review["file_hashes"].items():
        assert sha(root / fig / name) == digest, (fig, name)
    audit = json.loads((root / fig / "audit.json").read_text(encoding="utf-8"))
    for entry in audit["files"]:
        assert sha(root / fig / entry["name"]) == entry["sha256"], entry["name"]
    checks.append({"figure": fig, "review": review["id"], "files": len(review["file_hashes"]), "hashes_match": True})
assert sum(c["files"] for c in checks) == 33
residue = [str(p.relative_to(root)) for p in root.rglob("*") if p.name.startswith("._") or p.name in (".DS_Store", "__MACOSX")]
assert not residue, residue
print(json.dumps({"accepted_file_checks": checks, "metadata_residue": residue, "new_experiments": 0}, indent=2))
