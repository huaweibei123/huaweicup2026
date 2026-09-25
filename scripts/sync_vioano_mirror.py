"""Verify or fast-forward the public Vioano research mirror; never delete refs."""

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "huaweibei123/huaweicup2026"
TARGET = "Vioano/huaweicup2026"
# Signed sync channels and submission/delivery refs are transport state, not
# research material. Their frequent updates must not starve or inflate the mirror.
EXCLUDED_SOURCE_REFS = {"refs/heads/benchmark-fast-v1",
                        "refs/heads/benchmark-sync-v1"}
EXCLUDED_SOURCE_PREFIXES = ("refs/heads/benchmark-submissions/",
                            "refs/heads/benchmark-delivery/")


def excluded_transport(ref):
    return ref in EXCLUDED_SOURCE_REFS or ref.startswith(EXCLUDED_SOURCE_PREFIXES)


def run(argv, env=None):
    result = subprocess.run(argv, cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def account_env(login):
    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    env["GH_TOKEN"] = run([
        "gh", "auth", "token", "--hostname", "github.com", "--user", login
    ]).strip()
    actual = json.loads(run(["gh", "api", "user"], env))["login"]
    if actual != login:
        raise RuntimeError(f"Expected account {login}, got {actual}")
    return env


def git(args, env):
    # gh reads the command-scoped token from its environment. No token in argv,
    # remote URLs, Git configuration, output receipts, or global auth switching.
    return run([
        "git", "-c", "credential.helper=",
        "-c", "credential.helper=!gh auth git-credential", *args
    ], env)


def refs(remote, env):
    result = {}
    for line in git(["ls-remote", "--heads", "--tags", remote], env).splitlines():
        sha, ref = line.split()
        if not ref.endswith("^{}"):
            result[ref] = sha
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--push", action="store_true", help="Apply non-forced atomic push")
    parser.add_argument("--receipt", type=Path, help="New local JSON receipt path")
    args = parser.parse_args()
    if args.receipt and args.receipt.exists():
        raise RuntimeError("Use a new receipt path; previous evidence is not overwritten")
    common = Path(run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]).strip())
    lock = common / "vioano-mirror-sync.lock"
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    try:
        source_env = account_env("NikolaStarx")
        target_env = account_env("Vioano")
        for name, expected in [("origin", SOURCE), ("vioano", TARGET)]:
            if run(["git", "remote", "get-url", name]).strip() != f"https://github.com/{expected}.git":
                raise RuntimeError(f"Unexpected {name} remote; review configuration first")
        metadata = json.loads(run(["gh", "api", f"repos/{TARGET}"], target_env))
        if metadata["full_name"] != TARGET or metadata["private"] or metadata.get("visibility") != "public" or metadata["archived"]:
            raise RuntimeError("Target must be the active public Vioano research mirror")

        git(["fetch", "--no-tags", "origin",
             "refs/heads/*:refs/remotes/origin/*",
             "^refs/heads/benchmark-fast-v1",
             "^refs/heads/benchmark-sync-v1",
             "^refs/heads/benchmark-submissions/*",
             "^refs/heads/benchmark-delivery/*",
             "refs/tags/*:refs/mirror-source-tags/*"], source_env)
        source_all = refs("origin", source_env)
        excluded = sorted(ref for ref in source_all if excluded_transport(ref))
        source = {ref: sha for ref, sha in source_all.items()
                  if not excluded_transport(ref)}
        before = refs("vioano", target_env)
        refspecs = []
        for ref, sha in sorted(source.items()):
            local = ("refs/remotes/origin/" + ref.removeprefix("refs/heads/")
                     if ref.startswith("refs/heads/") else
                     "refs/mirror-source-tags/" + ref.removeprefix("refs/tags/"))
            if run(["git", "rev-parse", local]).strip() != sha:
                raise RuntimeError("Source changed during fetch; rerun for a coherent snapshot")
            if ref.startswith("refs/tags/") and ref in before and before[ref] != sha:
                raise RuntimeError(f"Tag divergence: {ref}; no overwrite allowed")
            refspecs.append(f"{local}:{ref}")
        changed = [ref for ref, sha in source.items() if before.get(ref) != sha]
        if changed:
            # Git rejects branch divergence. --atomic prevents partial updates;
            # absence of --force/--mirror/--prune protects history and extra refs.
            command = ["push", "--atomic", "--porcelain"]
            if not args.push:
                command.append("--dry-run")
            git([*command, "vioano", *refspecs], target_env)
        after = refs("vioano", target_env)
        matched = all(after.get(ref) == sha for ref, sha in source.items())
        if args.push and not matched:
            raise RuntimeError("Post-push refs did not match; inspect before retrying")
        receipt = {
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": SOURCE, "target": TARGET, "target_private": metadata["private"],
            "target_visibility": metadata["visibility"],
            "push_requested": args.push, "all_source_refs_match": matched,
            "excluded_transport_refs": excluded,
            "changed_refs": changed,
            "extra_target_refs_preserved": sorted(set(after) - set(source)),
            "source_snapshot": source, "target_snapshot": after,
            "limits": "Git refs only; not teammate checkout/read receipts or ChatGPT file access",
        }
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: v for k, v in receipt.items()
                          if k not in {"source_snapshot", "target_snapshot"}}, ensure_ascii=False))
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
