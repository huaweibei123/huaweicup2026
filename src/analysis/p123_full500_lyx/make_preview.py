from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import base64
import gzip
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(__file__).resolve().parent
OUT = ROOT / "results/a/p123-full500-lyx-20260925"
FIG = ROOT / "figures/a/p123-full500-lyx-20260925"
SOURCES = json.loads((SRC / "sources.json").read_text(encoding="utf-8"))
CACHE = OUT / "inputs"
_ARTIFACT_INDEX: dict[str, Path] | None = None
_ARTIFACT_JSON: dict[str, dict] = {}

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()

def read_fixed_feed(label: str, spec: dict) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{label}.json"
    if not target.exists() or git_blob_sha1(target.read_bytes()) != spec["blob_sha1"]:
        encoded = subprocess.check_output([
            "gh", "api", f"repos/{SOURCES['repository']}/git/blobs/{spec['blob_sha1']}", "--jq", ".content"
        ], text=True, timeout=120)
        raw = base64.b64decode("".join(encoded.split()))
        if git_blob_sha1(raw) != spec["blob_sha1"]:
            raise RuntimeError(f"{label} feed Git blob SHA mismatch: {git_blob_sha1(raw)}")
        target.write_bytes(raw)
    raw = target.read_bytes()
    if git_blob_sha1(raw) != spec["blob_sha1"]:
        raise RuntimeError(f"{label} cached feed SHA mismatch")
    return json.loads(raw)

def artifact_cache_path(spec: dict) -> Path:
    """Use content identity, not row identity, so repeated baseline refs share bytes."""
    suffix = ".json.gz" if spec["path"].endswith(".gz") else ".json"
    return CACHE / "artifacts" / f"{spec['sha256']}{suffix}"


def artifact_index(artifacts: Path) -> dict[str, Path]:
    global _ARTIFACT_INDEX
    if _ARTIFACT_INDEX is None:
        _ARTIFACT_INDEX = {
            sha256(candidate.read_bytes()): candidate
            for candidate in artifacts.iterdir()
            if candidate.is_file()
        }
    return _ARTIFACT_INDEX


def read_artifact(spec: dict) -> dict:
    """Read a feed-referenced JSON or gzip JSON artifact and verify its SHA-256."""
    if spec["sha256"] in _ARTIFACT_JSON:
        return _ARTIFACT_JSON[spec["sha256"]]
    artifacts = CACHE / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    target = artifact_cache_path(spec)
    if not target.exists() or sha256(target.read_bytes()) != spec["sha256"]:
        index = artifact_index(artifacts)
        raw = None
        # Reuse row-labelled cache files produced by the initial preview.
        candidate = index.get(spec["sha256"])
        if candidate is not None:
            raw = candidate.read_bytes()
        if raw is None:
            try:
                raw = subprocess.check_output(
                    ["git", "show", f"{spec['commit']}:{spec['path']}"],
                    stderr=subprocess.PIPE,
                    timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                encoded = subprocess.check_output([
                    "gh", "api",
                    f"repos/{SOURCES['repository']}/contents/{spec['path']}?ref={spec['commit']}",
                    "--jq", ".content"
                ], text=True, timeout=120)
                raw = base64.b64decode("".join(encoded.split()))
        if sha256(raw) != spec["sha256"]:
            raise RuntimeError(f"artifact SHA256 mismatch for {spec['path']}: {sha256(raw)}")
        target.write_bytes(raw)
        index[spec["sha256"]] = target
    raw = target.read_bytes()
    if sha256(raw) != spec["sha256"]:
        raise RuntimeError(f"cached artifact SHA256 mismatch for {spec['path']}")
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    parsed = json.loads(raw.decode("utf-8"))
    _ARTIFACT_JSON[spec["sha256"]] = parsed
    return parsed

def get(d: dict, *keys):
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return None

def metric(row: dict, key: str):
    metrics = row.get("metrics") or {}
    return get(metrics, key)

def baseline_makespan(row: dict, feed_spec: dict):
    base = row.get("baseline") or {}
    result_ref = base.get("result") or {}
    if result_ref.get("path") and result_ref.get("sha256"):
        result = read_artifact({"commit": feed_spec["commit"], "path": result_ref["path"], "sha256": result_ref["sha256"]})
        return get(result, "makespan_cycles", "makespan")
    metrics = base.get("metrics") or {}
    return get(metrics, "makespan_cycles", "makespan") or get(base, "makespan_cycles", "makespan")

def p1p2_table(feed: dict, label: str, feed_spec: dict):
    rows = []
    excluded = Counter()
    for row in feed.get("records", []):
        if row.get("status") != "ok":
            excluded["status_not_ok"] += 1
            continue
        m = metric(row, "makespan_cycles")
        b = baseline_makespan(row, feed_spec)
        if m is None or b is None or float(m) <= 0 or float(b) <= 0:
            excluded["missing_or_nonpositive_makespan"] += 1
            continue
        rows.append({"problem": label, "case_id": str(row["case_id"]), "cores": int(row["cores"]),
                     "makespan": float(m), "baseline": float(b), "speedup": float(b) / float(m),
                     "attempt_id": row.get("attempt_id"), "revision": row.get("revision")})
    return rows, dict(sorted(excluded.items()))


P3_IDENTITY_FIELDS = ("graph_sha256", "config_sha256", "official_sha256", "plan_sha256", "cores")


def p3_identity_mismatches(row: dict, pair: dict) -> list[str]:
    """Return missing/mismatched identity fields for a same-plan Cache comparison."""
    mismatches = []
    identity = row.get("identity") or {}
    for key in P3_IDENTITY_FIELDS:
        row_value = row.get(key) if key == "cores" else identity.get(key)
        pair_value = pair.get(key)
        if row_value is None or pair_value is None:
            mismatches.append(f"missing_{key}")
        elif str(row_value) != str(pair_value):
            mismatches.append(f"mismatch_{key}")
    return mismatches

def p3_table(feed: dict, feed_spec: dict):
    rows = []
    excluded = Counter()
    for row in feed.get("records", []):
        if row.get("status") != "ok":
            excluded["status_not_ok"] += 1
            continue
        pair = row.get("cache_pair") or {}
        mismatches = p3_identity_mismatches(row, pair)
        if mismatches:
            excluded.update(mismatches)
            continue
        cache = metric(row, "makespan_cycles")
        baseline = baseline_makespan(row, feed_spec)
        no_cache_ref = (pair.get("result") or {})
        no_cache = None
        if no_cache_ref.get("path") and no_cache_ref.get("sha256"):
            no_cache_result = read_artifact({"commit": feed_spec["commit"], "path": no_cache_ref["path"],
                                             "sha256": no_cache_ref["sha256"]})
            no_cache = get(no_cache_result, "makespan_cycles", "makespan")
        if no_cache is None:
            no_cache = get(pair, "no_cache_makespan_cycles", "makespan_cycles", "makespan")
        if (cache is None or no_cache is None or baseline is None
                or float(cache) <= 0 or float(no_cache) <= 0 or float(baseline) <= 0):
            excluded["missing_or_nonpositive_makespan"] += 1
            continue
        rows.append({"problem": "P3", "case_id": str(row["case_id"]), "cores": int(row["cores"]),
                     "cache": float(cache), "no_cache": float(no_cache), "baseline": float(baseline),
                     "speedup": float(baseline) / float(cache),
                     "cache_gain": float(no_cache) / float(cache),
                     "attempt_id": row.get("attempt_id"), "revision": row.get("revision")})
    return rows, dict(sorted(excluded.items()))

def summarize(rows: list[dict], fields: tuple[str, ...]):
    result = []
    for core in range(1, 6):
        subset = [r for r in rows if r["cores"] == core]
        entry = {"cores": core, "n": len(subset)}
        for field in fields:
            vals = [r[field] for r in subset]
            entry[field + "_mean"] = float(np.mean(vals)) if vals else None
        result.append(entry)
    return result


def batch_metadata(feed: dict) -> dict:
    fields = ("algorithm_id", "algorithm_name", "run_id", "solver_commit", "revision", "variant")
    result = {}
    for field in fields:
        values = {row.get(field) for row in feed.get("records", [])}
        if len(values) != 1 or None in values:
            raise RuntimeError(f"fixed batch does not have exactly one {field}: {sorted(str(v) for v in values)}")
        result[field] = values.pop()
    return result

def write_json(name: str, obj) -> None:
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def plot(p1_summary, p2_summary, p3_summary, batch_meta):
    plt.rcParams.update({"font.family": "sans-serif",
                         "font.sans-serif": ["Microsoft YaHei", "Noto Sans SC", "Arial", "DejaVu Sans"],
                         "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none"})
    colors = {"P1": "#0F4D92", "P2": "#42949E", "cache": "#3775BA", "no_cache": "#B64342", "ref": "#767676"}
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), gridspec_kw={"wspace": 0.28})
    x = np.arange(1, 6)
    for label, ax, summary, color in (("P1", axes[0], p1_summary, colors["P1"]),
                                      ("P2", axes[1], p2_summary, colors["P2"])):
        meta = batch_meta[label]
        y = [d["speedup_mean"] if d["speedup_mean"] is not None else np.nan for d in summary]
        ax.plot(x, y, marker="o", ms=6, lw=2.5, color=color, label="逐例加速比均值")
        ax.axhline(1, color=colors["ref"], lw=1.2, ls="--", label="单核参考线 y=1")
        for xx, yy, d in zip(x, y, summary):
            if np.isfinite(yy): ax.annotate(f"{yy:.2f}", (xx, yy), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
        ax.set(xlabel="核数", ylabel="平均加速比", xticks=x)
        ax.set_title(
            f"{label} · {meta['algorithm_id']}\nrun {meta['run_id']} · rev {meta['revision']} · n=100/core",
            fontsize=11.5,
            pad=10,
        )
        ax.grid(axis="y", alpha=0.22)
        ax.legend(frameon=False, fontsize=8, loc="best")
    cache = [d["cache_mean"] if d["cache_mean"] is not None else np.nan for d in p3_summary]
    no_cache = [d["no_cache_mean"] if d["no_cache_mean"] is not None else np.nan for d in p3_summary]
    gain = [d["cache_gain_mean"] if d["cache_gain_mean"] is not None else np.nan for d in p3_summary]
    ax = axes[2]
    ax.plot(x, no_cache, marker="s", lw=2.3, color=colors["no_cache"], label="无 Cache")
    ax.plot(x, cache, marker="o", lw=2.3, color=colors["cache"], label="只读 Cache")
    ax.set(xlabel="核数", ylabel="平均 Makespan（cycles）", xticks=x)
    meta = batch_meta["P3"]
    ax.set_title(
        f"P3 · {meta['algorithm_id']}\nrun {meta['run_id']} · rev {meta['revision']} · n=100/core",
        fontsize=11.5,
        pad=10,
    )
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, fontsize=8, loc="best")
    ax2 = ax.twinx()
    ax2.plot(x, gain, color="#9A4D8E", marker="D", lw=1.8, ms=5, label="逐例 CacheGain 均值")
    ax2.set_ylabel("CacheGain", color="#7A376F")
    ax2.tick_params(axis="y", colors="#7A376F")
    ax2.spines["top"].set_visible(False)
    for xx, yy in zip(x, gain):
        if np.isfinite(yy):
            ax2.annotate(f"{yy:.3f}×", (xx, yy), xytext=(0, 8), textcoords="offset points",
                         ha="center", fontsize=8, color="#7A376F")
    fig.suptitle("P1/P2/P3 固定全覆盖参考批次 · 主定量预览", fontsize=15, fontweight="bold", y=1.04)
    fig.text(0.5, -0.02, "P1/P2：逐例 official single-core M / current M 后取均值；P3：同图/配置/核数/方案的无 Cache 与只读 Cache 配对", ha="center", fontsize=9, color="#4D4D4D")
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(FIG / f"p123_full500_preview.{ext}", dpi=300, bbox_inches="tight")
    svg_path = FIG / "p123_full500_preview.svg"
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )
    plt.close(fig)

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    feeds = {label: read_fixed_feed(label, spec) for label, spec in SOURCES["feeds"].items()}
    batch_meta = {label: batch_metadata(feed) for label, feed in feeds.items()}
    (p1, p1_excluded), (p2, p2_excluded), (p3, p3_excluded) = (
        p1p2_table(feeds["P1"], "P1", SOURCES["feeds"]["P1"]),
        p1p2_table(feeds["P2"], "P2", SOURCES["feeds"]["P2"]),
        p3_table(feeds["P3"], SOURCES["feeds"]["P3"]),
    )
    p1s, p2s, p3s = summarize(p1, ("speedup",)), summarize(p2, ("speedup",)), summarize(p3, ("speedup", "cache", "no_cache", "cache_gain"))
    write_json("per_case.json", {"P1": p1, "P2": p2, "P3_verified_cache_pairs": p3})
    write_json("summary.json", {"P1": p1s, "P2": p2s, "P3": p3s})
    outputs = [
        "results/a/p123-full500-lyx-20260925/per_case.json",
        "results/a/p123-full500-lyx-20260925/summary.json",
        "figures/a/p123-full500-lyx-20260925/p123_full500_preview.png",
        "figures/a/p123-full500-lyx-20260925/p123_full500_preview.pdf",
        "figures/a/p123-full500-lyx-20260925/p123_full500_preview.svg",
    ]
    manifest = {"scope": SOURCES["scope"], "approval": SOURCES["approval"], "inputs": SOURCES["feeds"],
                "batches": batch_meta,
                "formulae": {"P1_P2": "arithmetic mean over cases of official_singlecore_makespan / current_makespan; k=1 is not forced to 1",
                               "P3_speedup": "arithmetic mean over cases of official_singlecore_makespan / current_cache_makespan; reported for provenance and anchor checking",
                               "P3_cache": "arithmetic mean over verified same-plan cases of no_cache_makespan / cache_makespan"},
                "valid_counts": {"P1": len(p1), "P2": len(p2), "P3_verified_pairs": len(p3)},
                "excluded_counts": {"P1": p1_excluded, "P2": p2_excluded, "P3": p3_excluded},
                "anchor_k1": {"P1_speedup": p1s[0]["speedup_mean"],
                              "P2_speedup": p2s[0]["speedup_mean"],
                              "P3_speedup": p3s[0]["speedup_mean"],
                              "P3_cache_gain": p3s[0]["cache_gain_mean"]},
                "outputs": outputs,
                "pair_verification": "P3 rows are accepted only when graph_sha256, config_sha256, official_sha256, plan_sha256, and cores match byte-identifying feed fields; artifact bytes are independently checked against SHA-256",
                "limitations": ["fixed full-coverage reference batches, not a claim of global optimum", "central board verification is separately attributed to the captain approval comment"],
                "execution_boundary": "read-only feed download/parse and plotting; no solver/E0/E1/E2 calls",
                "environment": {"python": sys.version, "matplotlib": matplotlib.__version__}}
    plot(p1s, p2s, p3s, batch_meta)
    manifest["output_sha256"] = {path: sha256((ROOT / path).read_bytes()) for path in outputs}
    write_json("manifest.json", manifest)
    print(json.dumps({"P1": len(p1), "P2": len(p2), "P3_verified_pairs": len(p3), "figure_dir": str(FIG)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
