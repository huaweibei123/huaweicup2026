"""Preserve current artifacts privately, normalize paths, and hash both forms."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from research.a.review.e2_windows_20260924.run_checks import redact


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--private", type=Path, required=True)
    p.add_argument("--original-from", type=Path)
    a = p.parse_args()
    a.private.mkdir(parents=True, exist_ok=False)
    rows = []
    for f in sorted(a.results.rglob("*")):
        if not f.is_file() or f.name == "ARTIFACT_MANIFEST.json":
            continue
        rel = f.relative_to(a.results)
        raw = f.read_bytes()
        backup = a.private / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(raw)
        published = raw
        if f.suffix in (".json", ".jsonl", ".txt"):
            published = redact(raw.decode("utf-8")).encode("utf-8")
        elif f.suffix == ".gz":
            decoded = gzip.decompress(raw).decode("utf-8")
            if redact(decoded) != decoded:
                raise RuntimeError("Compressed result unexpectedly contains private paths")
        if published != raw:
            f.write_bytes(published)
        original = raw
        if a.original_from and (a.original_from / rel).is_file():
            original = (a.original_from / rel).read_bytes()
        rows.append(dict(path=rel.as_posix(), original_sha256=hashlib.sha256(original).hexdigest(),
                         published_sha256=hashlib.sha256(published).hexdigest(), bytes=len(published),
                         changed=published != original))
    manifest = dict(files=rows,
        note="original_sha256 hashes the pre-publication artifact copy, not necessarily raw subprocess output. Native/provisioned command records separately carry private_raw_sha256; preflight stderr was normalized at capture and its original was not retained. Private copies remain outside Git.")
    (a.results / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(files=len(rows), redacted=sum(r["changed"] for r in rows))))


if __name__ == "__main__":
    main()
