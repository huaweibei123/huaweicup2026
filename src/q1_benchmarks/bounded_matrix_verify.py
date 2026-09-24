"""Read-only Git-byte verification of feed and recursively referenced run files.

This supplements board preflight with optional log/diagnostic/stdout references.
One persistent git cat-file process avoids one subprocess per artifact. No
solver, evaluator, network, or central-ledger access is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("commit")
    p.add_argument("feeds", nargs="+")
    args = p.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        p.error("full commit SHA required")
    child = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    def blob(path):
        if "\n" in path or "\r" in path or path.startswith("/") or ".." in Path(path).parts:
            raise RuntimeError("Invalid artifact path")
        child.stdin.write(f"{args.commit}:{path}\n".encode())
        child.stdin.flush()
        header = child.stdout.readline().decode().strip().split()
        if len(header) != 3 or header[1] != "blob":
            raise RuntimeError(f"Missing Git blob: {path}")
        raw = child.stdout.read(int(header[2]))
        if child.stdout.read(1) != b"\n":
            raise RuntimeError("Invalid cat-file framing")
        return raw
    refs, checked, feeds = {}, set(), []
    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))):
                path, digest = value["path"], value["sha256"]
                if path in refs and refs[path] != digest:
                    raise RuntimeError(f"Conflicting artifact hash: {path}")
                refs[path] = digest
            for v in value.values():
                collect(v)
        elif isinstance(value, list):
            for v in value:
                collect(v)
    total_bytes = 0
    try:
        for path in args.feeds:
            raw = blob(path)
            obj = json.loads(raw)
            feeds.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "records": len(obj["records"])})
            collect(obj)
        while pending := sorted(set(refs) - checked):
            for path in pending:
                raw = blob(path)
                if hashlib.sha256(raw).hexdigest() != refs[path]:
                    raise RuntimeError(f"Artifact hash mismatch: {path}")
                total_bytes += len(raw)
                checked.add(path)
                if Path(path).name == "run.json":
                    collect(json.loads(raw))
        print(json.dumps({"valid": True, "commit": args.commit, "feeds": feeds,
                          "unique_artifacts_checked": len(checked), "artifact_bytes_checked": total_bytes,
                          "scope": "fixed Git bytes and SHA256 only; no independent algorithm rerun"}, indent=2))
    finally:
        child.stdin.close()
        child.stdout.close()
        child.wait()


if __name__ == "__main__":
    main()
