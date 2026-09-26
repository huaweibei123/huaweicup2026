"""Rebuild the P2 multicore comparison from Fang's fixed handoff bundle.

This program reads published results only. It never invokes a solver or evaluator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from zipfile import ZipFile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "deliverables/a/fig53-captain-handoff-20260927"
ZIP = HANDOFF / "fig5-3-captain-rework-e5b785c.zip"
OUTPUT = ROOT / "figures/a/fig53-captain-rework-20260927"
ZIP_SHA256 = "de2563406e59a599d0792d11139a2ad99732967bc65c2e3600287a9bf5539e27"
MEMBER_RESULTS_COMMIT = "178a3673bd238b20772211427b8134b6db35f5af"
MAIN_RESULTS_COMMIT = "1c00079aadbd071de62db17686d5ba3fed1da0f2"
MAIN_SOLVER_COMMIT = "c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f"
METHODS = ("tensor", "gap", "c665", "F1")
METHOD_SOLVER_COMMITS = {
    "tensor": "e64723bdf99669c44f76d8e90ab0379a8578522e",
    "gap": "384b6c2a7ff937ca44180dee09a9d4bcaea0c50d",
    "c665": MAIN_SOLVER_COMMIT,
    "F1": "4a501d7f4a8b780263e097a963e12dcb66178e69",
}
SOURCE_FILES = {
    "tensor": "inputs/tensor-per-cell.csv",
    "gap": "inputs/gap-per-cell.csv",
    "c665": "inputs/c665-completed-summary.json",
    "F1": "inputs/F1-per-cell.csv",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_handoff() -> tuple[dict[str, bytes], dict]:
    assert digest(ZIP.read_bytes()) == ZIP_SHA256, "The published handoff ZIP changed"
    expected = json.loads((HANDOFF / "MANIFEST.sha256.json").read_text())
    with ZipFile(ZIP) as archive:
        raw = {name: archive.read(name) for name in archive.namelist()}
    assert set(raw) == set(expected) | {"MANIFEST.sha256.json"}
    for name, sha256 in expected.items():
        assert Path(name).name and ".." not in Path(name).parts
        assert digest(raw[name]) == sha256, f"Handoff byte mismatch: {name}"
    specs = json.loads(raw["review/fig53-required-methods.json"].decode("utf-8-sig"))
    return raw, specs


def csv_rows(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def build_rows(raw: dict[str, bytes], specs: dict) -> list[dict]:
    records = []
    baseline_by_case: dict[str, int] = {}
    baseline_receipts: dict[str, str] = {}
    expected_sources = {entry["sha256"] for entry in specs["sources"]}
    assert {digest(raw[path]) for path in SOURCE_FILES.values()} == expected_sources

    for method in ("tensor", "gap", "F1"):
        for source in csv_rows(raw[SOURCE_FILES[method]]):
            case = source["case_id"].zfill(3)
            cores = int(source["cores"])
            baseline = int(source["baseline_cycles"])
            makespan = int(source["makespan_cycles"])
            assert baseline > 0 and makespan > 0
            prior = baseline_by_case.setdefault(case, baseline)
            assert prior == baseline, f"Official single-core baseline differs for case {case}"
            receipt = source["baseline_receipt_sha256"]
            assert baseline_receipts.setdefault(case, receipt) == receipt
            assert abs(float(source["speedup"]) - baseline / makespan) < 1e-12
            records.append(
                {
                    "case": case,
                    "cores": cores,
                    "method": method,
                    "baseline": baseline,
                    "makespan": makespan,
                    "speedup": baseline / makespan,
                    "source_commit": MEMBER_RESULTS_COMMIT,
                    "result_sha256": source["result_sha256"],
                }
            )

    main = json.loads(raw[SOURCE_FILES["c665"]])
    assert main["status"] == "completed" and main["accepted_cells"] == 500
    assert main["solver_commit"] == MAIN_SOLVER_COMMIT and len(main["rows"]) == 500
    for source in main["rows"]:
        assert source["status"] == "accepted"
        case = str(source["case"]).zfill(3)
        makespan = int(source["official"]["makespan"])
        baseline = baseline_by_case[case]  # NOT source['baseline']: that is an optimized predecessor.
        assert makespan > 0
        records.append(
            {
                "case": case,
                "cores": int(source["cores"]),
                "method": "c665",
                "baseline": baseline,
                "makespan": makespan,
                "speedup": baseline / makespan,
                "source_commit": MAIN_RESULTS_COMMIT,
                "result_sha256": source["official"]["result_sha256"],
            }
        )

    assert len(baseline_by_case) == 100 and sorted(baseline_by_case) == [f"{i:03d}" for i in range(1, 101)]
    assert baseline_by_case["002"] == 261945  # Independently checked official A baseline.
    keys = [(r["method"], r["case"], r["cores"]) for r in records]
    assert len(keys) == len(set(keys)) == 1600
    for method in METHODS:
        actual = {(r["case"], r["cores"]) for r in records if r["method"] == method}
        cores = range(1, 6) if method != "F1" else (5,)
        expected = {(f"{case:03d}", core) for case in range(1, 101) for core in cores}
        assert actual == expected, f"Missing or unexpected coordinates in {method}"
    return sorted(records, key=lambda r: (METHODS.index(r["method"]), r["cores"], r["case"]))


def summarize(records: list[dict], specs: dict) -> list[dict]:
    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    for record in records:
        groups[(record["method"], record["cores"])].append(record["speedup"])
    summary = []
    expected_means = {"tensor": "all500", "gap": "gap-full500", "c665": "c665", "F1": "frontier-k5-100"}
    for (method, cores), values in sorted(groups.items(), key=lambda e: (METHODS.index(e[0][0]), e[0][1])):
        assert len(values) == 100
        observed = fmean(values)
        target = specs["means"][expected_means[method]][str(cores)]
        assert abs(observed - target) < 1e-9, (method, cores, observed, target)
        summary.append(
            {
                "method": method,
                "cores": cores,
                "n": len(values),
                "mean_speedup": observed,
                "mean_observed_speedup": observed,
                "display_policy": "observed_mean",
            }
        )
    assert len(summary) == 16
    return summary


def choose_chinese_font() -> str:
    available = {font.name for font in font_manager.fontManager.ttflist}
    # Prefer a TrueType CJK font for editable PDF text; macOS PingFang is CFF/TTC.
    for family in ("Arial Unicode MS", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "PingFang SC", "Hiragino Sans GB"):
        if family in available:
            return family
    raise RuntimeError("No installed Chinese font is available for this paper figure")


def draw(summary: list[dict], output: Path) -> str:
    font = choose_chinese_font()
    plt.rcParams.update(
        {
            "font.family": font,
            "font.size": 8,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "fig53-captain-20260927",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    by_method = defaultdict(dict)
    for record in summary:
        by_method[record["method"]][record["cores"]] = record["mean_speedup"]
    colors = {"tensor": "#68798B", "gap": "#0E8A7F", "c665": "#214B9A", "F1": "#BE4A36"}
    names = {"tensor": "张量分组", "gap": "空闲区间调整", "c665": "本文主方法", "F1": "容量保护 F1"}
    styles = {"tensor": ("--", "^"), "gap": ("-.", "s"), "c665": ("-", "o")}

    width_in = 160 / 25.4
    fig = plt.figure(figsize=(width_in, 88 / 25.4), facecolor="white")
    grid = fig.add_gridspec(1, 2, width_ratios=(2.55, 1), left=0.10, right=0.975, top=0.88, bottom=0.17, wspace=0.34)
    ax = fig.add_subplot(grid[0, 0])
    detail = fig.add_subplot(grid[0, 1])
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E6EAF0", linewidth=0.6)
    ax.plot(range(1, 6), range(1, 6), color="#AFB7C1", linewidth=1.0, linestyle=":", label="理想线性加速")
    for method in ("tensor", "gap", "c665"):
        x = list(range(1, 6))
        y = [by_method[method][core] for core in x]
        line, marker = styles[method]
        ax.plot(x, y, color=colors[method], linewidth=1.75 if method == "c665" else 1.35, linestyle=line,
                marker=marker, markersize=4.3, markerfacecolor="white" if method != "c665" else colors[method],
                markeredgewidth=1.0, label=names[method], zorder=3 if method == "c665" else 2)
    ax.scatter([5], [by_method["F1"][5]], s=44, marker="D", facecolor="white", edgecolor=colors["F1"],
               linewidth=1.45, label=names["F1"], zorder=6)
    ax.set_xlim(0.92, 5.12)
    ax.set_ylim(0.83, 5.16)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xlabel("NPU 核心数", labelpad=5)
    ax.set_ylabel("平均加速比（倍）", labelpad=6)
    ax.legend(loc="upper left", ncol=2, fontsize=7.0, frameon=False, columnspacing=0.8,
              handlelength=2.0, labelspacing=0.55, borderaxespad=0.2)

    # Separate categorical rows resolve the true 0.008 difference at k=5.
    order = ("c665", "tensor", "F1", "gap")
    detail.set_title("五核心结果", fontsize=8.5, loc="left", pad=10)
    detail.set_axisbelow(True)
    detail.grid(axis="x", color="#E6EAF0", linewidth=0.6)
    for y, method in zip(range(4, 0, -1), order):
        value = by_method[method][5]
        detail.scatter([value], [y], color=colors[method] if method != "F1" else "white",
                       edgecolor=colors[method], marker="D" if method == "F1" else "o", s=24, zorder=4)
        detail.text(5.00, y, f"{value:.3f}", ha="right", va="center", fontsize=7.2, color=colors[method])
    detail.set_yticks([4, 3, 2, 1], [names[m] for m in order])
    detail.tick_params(axis="y", length=0, pad=4, labelsize=7.0)
    detail.tick_params(axis="x", labelsize=7.0)
    detail.set_xlim(3.5, 5.05)
    detail.set_xticks([3.5, 4.0, 4.5])
    detail.set_ylim(0.45, 4.55)
    detail.set_xlabel("平均加速比（倍）", labelpad=5, fontsize=7.5)
    for spine in ("left", "bottom"):
        detail.spines[spine].set_color("#B7C0CA")
        ax.spines[spine].set_color("#B7C0CA")
    for suffix in ("pdf", "svg", "png"):
        path = output / f"fig53_p2_speedup.{suffix}"
        metadata = {"Creator": "fig53_rework.py", "CreationDate": datetime(2026, 9, 27, tzinfo=timezone.utc)} if suffix == "pdf" else None
        if suffix == "svg":
            metadata = {"Date": "2026-09-27", "Creator": "fig53_rework.py"}
        fig.savefig(path, dpi=300, facecolor="white", metadata=metadata)
        if suffix == "svg":
            # Matplotlib leaves spaces at the end of SVG path-data lines.
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")
    plt.close(fig)
    return font


def write_csv(path: Path, columns: list[str], records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def write_hash_records(output: Path) -> None:
    deliverables = (
        "fig53_p2_speedup.pdf",
        "fig53_p2_speedup.svg",
        "fig53_p2_speedup.png",
        "per_case_speedup.csv",
        "method_core_summary.csv",
        "validation.json",
        "caption.md",
        "README.md",
        "self-check.md",
    )
    entries = []
    for name in deliverables:
        path = output / name
        contents = path.read_bytes()
        entries.append({"path": name, "sha256": digest(contents), "bytes": len(contents)})
    manifest = {
        "schema": "fig53-delivery-v1",
        "source_commit": "6ac4ec28582212c9fab967ceab5e09e796dbadba",
        "source_zip_sha256": ZIP_SHA256,
        "script_sha256": digest(Path(__file__).read_bytes()),
        "command": "uv run --locked python src/analysis/fig53_rework.py --figure 5-3",
        "outputs": entries,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audited = {entry["path"]: entry["sha256"] for entry in entries}
    audited["manifest.json"] = digest(manifest_path.read_bytes())
    audit = {
        "schema": "fig53-audit-v1",
        "command": manifest["command"],
        "script_path": str(Path(__file__).relative_to(ROOT)),
        "script_sha256": manifest["script_sha256"],
        "source_zip_path": str(ZIP.relative_to(ROOT)),
        "source_zip_sha256": ZIP_SHA256,
        "files": audited,
        "remote_git_bytes_checked": False,
        "note": "audit.json deliberately has no self-hash; remote Git objects must be checked after publication.",
    }
    (output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", required=True, choices=["5-3"])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw, specs = read_handoff()
    records = build_rows(raw, specs)
    summary = summarize(records, specs)
    write_csv(output / "per_case_speedup.csv", ["case", "cores", "method", "baseline", "makespan", "speedup", "source_commit", "result_sha256"], records)
    write_csv(output / "method_core_summary.csv", ["method", "cores", "n", "mean_speedup", "mean_observed_speedup", "display_policy"], summary)
    font = draw(summary, output)
    validation = {
        "handoff_commit": "6ac4ec28582212c9fab967ceab5e09e796dbadba",
        "handoff_zip_sha256": ZIP_SHA256,
        "source_file_sha256": {path: digest(raw[path]) for path in SOURCE_FILES.values()},
        "method_cells": {method: sum(r["method"] == method for r in records) for method in METHODS},
        "summary": summary,
        "baseline_case_002": 261945,
        "main_solver_commit": MAIN_SOLVER_COMMIT,
        "method_solver_commits": METHOD_SOLVER_COMMITS,
        "font": font,
        "python_version": sys.version.split()[0],
        "matplotlib_version": matplotlib.__version__,
        "platform": platform.platform(),
        "figure_width_mm": 160,
        "solver_or_evaluator_calls": 0,
        "scope": "Published per-cell CSVs and completed summary were recomputed; underlying 1,500 official result files were not rerun or reaudited.",
    }
    (output / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output == OUTPUT and all((output / name).exists() for name in ("README.md", "caption.md", "self-check.md")):
        write_hash_records(output)
    print(json.dumps({"output": str(output), "font": font, "cells": validation["method_cells"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
