"""Create the one-case, source-pinned preparation-only 014/K1 capsule locally.

No evaluator is imported or called. Output is a ZIP for a coordinator-approved
CPU Standard window; package creation is not permission to start a VM.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile


E2_COMMIT = "5f3c1f536dc9c63aefdbc1762fbd023e8a6aea57"
OLD_E2_COMMIT = "603b0741e21c449d3db652ebd67c94f2dc014cc9"
OLD_PROFILE_COMMIT = "e4f7b13e4af04914a1264a650831a3959f14a373"
P2_MANIFEST_COMMIT = "ee4fe0282ca2ff5d73bb23d54b1c213909e1401c"
OLD_ZIP_SHA = "bdc28f73c3001ec4385143a48a80538f1147067812471a1ddce6d9d4b13148ca"


def git_blob(revision: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{revision}:{path}"])


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def add(z: zipfile.ZipFile, name: str, raw: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, raw, compresslevel=6)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: q2_rank_prep_package.py OUTPUT_ZIP")
    destination = Path(sys.argv[1]).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    old_manifest = json.loads(git_blob(P2_MANIFEST_COMMIT,
        "results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json"))
    if old_manifest["e2_commit"] != OLD_E2_COMMIT or len(old_manifest["e2_sources"]) != 50:
        raise ValueError("old source manifest identity mismatch")
    source_names = [*old_manifest["e2_sources"], "research/a/e2_search/_rank_b.py"]
    archive = subprocess.check_output(["git", "archive", "--format=tar", E2_COMMIT,
                                       "--", *source_names])
    source_files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            if member.isfile():
                if member.name not in source_names or member.name in source_files:
                    raise ValueError("unexpected source archive member")
                source_files[member.name] = tar.extractfile(member).read()
    if set(source_files) != set(source_names):
        raise ValueError("incomplete E2 source archive")
    for name, expected in old_manifest["e2_sources"].items():
        if name not in ("research/a/e2_search/scene_b.py", "research/a/e2_search/pool.py"):
            if sha(source_files[name]) != expected:
                raise ValueError("unintended E2 source drift: " + name)

    old_zip = git_blob(OLD_PROFILE_COMMIT,
        "results/a/q2-nikolastarx/preparation-profile-20260925/run/results.zip")
    if sha(old_zip) != OLD_ZIP_SHA:
        raise ValueError("old profile archive drift")
    with zipfile.ZipFile(io.BytesIO(old_zip)) as old:
        inputs = {name: old.read("inputs/" + name) for name in
                  ("graph.json", "plan.json", "config.txt")}
        old_report = json.loads(old.read("output/report.json"))
    for name, field in (("graph.json", "graph_sha256"),
                        ("plan.json", "plan_sha256"),
                        ("config.txt", "config_sha256")):
        expected = old_report.get(field)
        if expected is not None and sha(inputs[name]) != expected:
            raise ValueError("old profile input drift: " + name)
    runner_name = "q2_rank_prep_differential.py"
    runner = git_blob(head, "scripts/" + runner_name)
    files = {"e2-src/" + name: raw for name, raw in source_files.items()}
    files.update(inputs)
    for name in ("pyproject.toml", "uv.lock"):
        files[name] = git_blob(E2_COMMIT, name)
    files[runner_name] = runner
    manifest = {"schema": "q2-rank-prep-014k1-v1", "source_commit": E2_COMMIT,
                "old_source_commit": OLD_E2_COMMIT, "runner_commit": head,
                "old_profile_commit": OLD_PROFILE_COMMIT,
                "old_results_zip_sha256": OLD_ZIP_SHA,
                "old_prepared_sha256": old_report["prepared_sha256"],
                "limits": {"preparations": 1, "E0": 0, "native": 0,
                           "workers": 1, "seconds": 180,
                           "rss_bytes": 4 << 30, "retries": 0},
                "files": {name: sha(raw) for name, raw in sorted(files.items())}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w") as out:
        for name, raw in sorted(files.items()):
            add(out, name, raw)
        add(out, "old-results.zip", old_zip)
        add(out, "manifest.json", (json.dumps(manifest, sort_keys=True, indent=2)+"\n").encode())
    print(json.dumps({"capsule": str(destination), "sha256": sha(destination.read_bytes()),
                      "bytes": destination.stat().st_size,
                      "source_files": len(source_files), "runner_commit": head}))


if __name__ == "__main__":
    main()
