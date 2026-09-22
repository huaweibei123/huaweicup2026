"""Read-only readiness check. Never creates identities, issues or branches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = "huaweibei123/huaweicup2026"


def main() -> int:
    report = {"scope": "read-only; not a live rehearsal result", "checks": {}}
    errors = []

    def run(name, args, parse=False):
        try:
            result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                    encoding="utf-8", timeout=45, check=True)
            value = json.loads(result.stdout) if parse else result.stdout.strip()
            report["checks"][name] = value
            return value
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            # Do not dump authentication/transport stderr into a shareable report.
            errors.append(f"{name}: {type(exc).__name__}; inspect this command locally")
            return None

    run("git", ["git", "--version"])
    node = run("node", ["node", "--version"])
    if node and int(node.removeprefix("v").split(".")[0]) < 22:
        errors.append("Use Node.js 22+ for the project rehearsal")
    node_platform = run("node_platform", ["node", "-p", "process.platform"])
    patch_path = ROOT / "docs" / "system-atlas-windows-patch.json"
    patch = json.loads(patch_path.read_text(encoding="utf-8")) if patch_path.is_file() else None
    extra_path = ROOT / "docs" / "system-atlas-competition-patch.json"
    extra_patch = json.loads(extra_path.read_text(encoding="utf-8")) if extra_path.is_file() else None
    patch_verified = False
    run("gh", ["gh", "--version"])
    run("commit", ["git", "rev-parse", "HEAD"])
    origin = run("origin", ["git", "remote", "get-url", "origin"])
    if origin not in (f"https://github.com/{REPO}.git", f"https://github.com/{REPO}",
                      f"git@github.com:{REPO}.git", f"ssh://git@github.com/{REPO}.git"):
        errors.append("origin must be the shared team repository")
    run("worktree", ["git", "status", "--short"])
    run("actor", ["gh", "api", "user", "--jq", ".login"])
    permissions = run("permissions", ["gh", "api", f"repos/{REPO}",
                                      "--jq", ".permissions"], parse=True)
    if permissions and not permissions.get("push"):
        errors.append("GitHub account lacks repository push permission")
    run("remote_read", ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"])
    for name in ("system-atlas", "scientific-figure-making"):
        manifest = json.loads((ROOT / "docs" / f"{name}-install.json").read_text())
        mismatched = []
        overrides = {}
        if name == "system-atlas" and patch:
            originals = {item["path"]: item["sha256"] for item in manifest["files"]}
            if patch["upstream_commit"] != manifest["commit"]:
                errors.append("Windows patch upstream commit mismatch")
            else:
                for item in patch["files"]:
                    if originals.get(item["path"]) != item["upstream_sha256"]:
                        errors.append("Windows patch original hash mismatch: " + item["path"])
                    else:
                        overrides[item["path"]] = item["patched_sha256"]
        windows_override_count = len(overrides)
        if name == "system-atlas" and extra_patch:
            originals = {item["path"]: item["sha256"] for item in manifest["files"]}
            if extra_patch["upstream_commit"] != manifest["commit"]:
                errors.append("Competition patch upstream commit mismatch")
            else:
                for item in extra_patch["files"]:
                    if originals.get(item["path"]) != item["upstream_sha256"] or item["path"] in overrides:
                        errors.append("Competition patch original hash mismatch or duplicate: " + item["path"])
                    else:
                        overrides[item["path"]] = item["patched_sha256"]
        for item in manifest["files"]:
            path = ROOT / manifest["install_path"] / item["path"]
            expected = overrides.get(item["path"], item["sha256"])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                mismatched.append(item["path"])
        # Added local patch files have no upstream entry, but must also be hashed.
        if name == "system-atlas" and extra_patch:
            for item in extra_patch["files"]:
                if item["path"] not in originals:
                    added = ROOT / manifest["install_path"] / item["path"]
                    if not added.is_file() or hashlib.sha256(added.read_bytes()).hexdigest() != overrides.get(item["path"]):
                        mismatched.append(item["path"])
        report["checks"][name] = {"commit": manifest["commit"], "mismatched": mismatched}
        if name == "system-atlas" and patch:
            patch_verified = not mismatched and windows_override_count == len(patch["files"]) and "design/authority.mjs" in overrides
            report["checks"][name]["local_patch"] = {"id": patch["id"], "verified": patch_verified}
        if name == "system-atlas" and extra_patch:
            report["checks"][name]["competition_patch"] = extra_patch["id"]
        if mismatched:
            errors.append(f"{name}: files differ from installation manifest")
    if node_platform == "win32":
        if not patch_verified:
            errors.append("Native Windows requires the verified local compatibility patch or Linux/WSL2")
        report["checks"]["windows_durability"] = "File fsync retained; directory rename metadata is NOT guaranteed durable across power loss. See WINDOWS_COMPAT.md."
    run("model", ["node", str(ROOT / ".agents/skills/system-atlas/bin/system-atlas.mjs"),
                  "validate", "tests/rehearsal/system.json", "--repo-root", ".", "--json"], parse=True)
    report.update(ok=not errors, errors=errors)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
