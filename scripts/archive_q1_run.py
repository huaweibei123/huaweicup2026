"""Store full raw E0 outputs without flooding code review with JSON lines."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

RAW_NAMES = {"result.json", "trace.json", "stdout.txt", "stderr.txt", "summary.log"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    output = args.run / "execution-evidence.tar.xz"
    if output.exists():
        raise FileExistsError(output)
    members = []
    with tarfile.open(output, "w:xz") as archive:
        for p in sorted(args.run.rglob("*")):
            if p.is_file() and p.name in RAW_NAMES:
                data = p.read_bytes()
                relative = str(p.relative_to(args.run))
                item = tarfile.TarInfo(relative)
                item.size, item.mode = len(data), 0o644
                archive.addfile(item, io.BytesIO(data))
                members.append({"path": relative, "bytes": len(data), "sha256": sha(data)})
    with tarfile.open(output) as archive:
        assert archive.getnames() == [m["path"] for m in members]
        for member in members:
            assert sha(archive.extractfile(member["path"]).read()) == member["sha256"]
    receipt = {"archive": output.name, "bytes": output.stat().st_size, "sha256": sha(output.read_bytes()),
               "all_payload_hashes_equal": True, "members": members,
               "scope": "Exact raw CLI outputs, including captured runtime paths; no result normalization"}
    (args.run / "execution-evidence.manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(args.run, len(members), output.stat().st_size)


if __name__ == "__main__":
    main()
