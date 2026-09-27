"""Archive downloaded Pro ZIP payloads losslessly, with portable provenance.

Solid compression avoids storing thousands of repeated JSON graphs in Git.
No downloaded program is executed. Original ZIP hashes and every member hash
remain in the manifest; archive payload bytes are verified after compression.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile

PACKAGES = {
    "pro1-r3": ("NPU_A_Structural_Prototypes_R3.zip", "6ab2d851-0348-83e8-ab24-02db57b01aea"),
    "pro2-r2-prototype": ("HuaweiCup_A_Round2_Prototype.zip", "6ab39af5-bcf4-83e8-a5ec-a093f60f2039"),
    "pro2-r2-evidence": ("HuaweiCup_A_Round2_Full_E0_Evidence.zip", "6ab39af5-bcf4-83e8-a5ec-a093f60f2039"),
    "pro3-r2": ("huaweicup_route3_round2_evidence.zip", "6ab39c90-71e4-83e8-bc98-4c2e1563dacf"),
    "pro4-initial": ("HuaweiCup_A_R4_Evidence.zip", "6ab3ab72-a190-83e8-b333-106a0da92cff"),
    "pro4-followup": ("HuaweiCup_Route4_Evidence.zip", "6ab3ab72-a190-83e8-b333-106a0da92cff"),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def split_large_archive(destination):
    """Keep every Git blob below GitHub's size limit; lossless concatenation."""
    if destination.stat().st_size <= 48 * 1024 * 1024:
        return []
    parts = []
    joined_hash = hashlib.sha256()
    expected = digest(destination.read_bytes())
    with destination.open("rb") as source:
        while data := source.read(48 * 1024 * 1024):
            target = destination.with_name(destination.name + f".part{len(parts):03d}")
            target.write_bytes(data)
            reread = target.read_bytes()
            joined_hash.update(reread)
            parts.append({"path": target.name, "bytes": len(reread), "sha256": digest(reread)})
    assert joined_hash.hexdigest() == expected
    destination.unlink()  # Generated archive only; original downloaded ZIP stays intact.
    return parts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("downloads", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    summaries = []
    for label, (filename, chat_id) in PACKAGES.items():
        source = args.downloads / filename
        destination = args.output / (label + ".tar.xz")
        members = []
        with zipfile.ZipFile(source) as archive:
            assert archive.testzip() is None, filename
            names = archive.namelist()
            assert len(names) == len(set(names)), "duplicate ZIP paths"
            with tarfile.open(destination, "w:xz", preset=6) as target:
                for name in sorted(names):
                    path = PurePosixPath(name)
                    assert not path.is_absolute() and ".." not in path.parts
                    if name.endswith("/"):
                        continue
                    data = archive.read(name)
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mode = 0o644
                    target.addfile(info, io.BytesIO(data))
                    members.append({"path": name, "bytes": len(data), "sha256": digest(data)})
                    # Readable reports alongside the immutable complete payload.
                    if name.endswith(".md") and (len(path.parts) == 2 or path.name == "RESULTS.md"):
                        report = args.output / "reports" / label / path.name
                        report.parent.mkdir(parents=True, exist_ok=True)
                        report.write_bytes(data)
        with tarfile.open(destination) as check:
            assert check.getnames() == [m["path"] for m in members]
            for member in members:
                assert digest(check.extractfile(member["path"]).read()) == member["sha256"]
        summary = {
            "label": label, "source_filename": filename,
            "source_bytes": source.stat().st_size, "source_sha256": digest(source.read_bytes()),
            "source_chat": "https://chatgpt.com/g/g-p-6ab2d820c86081918067a0c6d5eb1ab6/c/" + chat_id,
            "acquired_date": "2026-09-24", "acquisition": "in-app browser download event; local bytes checked",
            "archive": destination.name, "archive_bytes": destination.stat().st_size,
            "archive_sha256": digest(destination.read_bytes()), "payload_files": len(members),
            "zip_crc_valid": True, "all_repacked_payload_hashes_equal": True,
            "validation_scope": "Byte integrity only; author experiments and proofs are not independently accepted",
        }
        summary["parts"] = split_large_archive(destination)
        (args.output / (label + ".manifest.json")).write_text(json.dumps({**summary, "members": members}, ensure_ascii=False, indent=2) + "\n")
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    (args.output / "manifest.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
