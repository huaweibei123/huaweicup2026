from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures/a/p123-fig-5-3-lyx-20260926"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    files = []
    roles = {
        "fig53_p2_speedup.svg": "svg",
        "fig53_p2_speedup.png": "png",
        "fig53_p2_speedup.pdf": "pdf",
        "plot_figures.py": "source",
        "caption.md": "caption",
        "self-check.md": "self_check",
        "per_case_speedup.csv": "input",
        "method_core_summary.csv": "input",
        "README.md": "notes",
        "manifest.json": "notes",
    }
    for name, role in roles.items():
        path = OUT / name
        files.append({"name": name, "role": role, "sha256": sha(path)})
    audit = {
        "schema": "figure-auto-review-v1",
        "figure_id": "fig-5-3",
        "primary": "fig53_p2_speedup.svg",
        "files": files,
        "command": "uv run python src/analysis/p123_figures_lyx/plot_all.py --figure 5-3",
        "sources": [{
            "path": "results/a/p123-full500-lyx-20260925/per_case.json",
            "commit": "5f4b7036ef7d05fcc88242742ad9ac0ab75b2b5a",
            "git_blob": "018ebde9b33b64428fda0db4ad05746b1ec32fbf",
            "sha256": "122da1335cf8f70e3db472ff84270cb3fc17690fcb3200607555c9dad7545847",
            "working_copy_sha256": "074bfa55b25acb60504780ff3107f9c28fef3ba58ef750bee1bbb0996fb9cdfc",
        }],
        "local_inputs": [{
            "path": "results/a/p123-full500-lyx-20260925/inputs/P2.json",
            "sha256": sha(ROOT / "results/a/p123-full500-lyx-20260925/inputs/P2.json"),
            "published": False,
            "reason": "large normalized input is gitignored; the published per_case.json is the reproducible plot feed",
        }],
        "units": {"makespan": "cycles", "wall": "s", "bytes": "B"},
        "panels": [
            {"id": "speedup", "title": "P2 mean per-case speedup"},
            {"id": "ideal", "title": "Ideal linear reference"},
        ],
        "tables": {"metrics": "per_case_speedup.csv", "summary": "method_core_summary.csv"},
        "coverage": {"cases": 100, "cores": [1, 2, 3, 4, 5], "cells": 500,
                      "method": "q2-adaptive-budget", "per_core": 100},
        "criteria": [
            "k=1 display anchor is 1.0; observed k=1 ratios remain in per_case_speedup.csv.",
            "The single plotted method has 100 cases at every core count.",
            "All ratios use the common per-case single-core denominator; no historical splice.",
        ],
        "status": "ready_for_human_review",
        "limitations": [
            "Only q2-adaptive-budget has complete coverage in this fixed source batch.",
            "SVG/PDF were generated and hashes checked; desktop reader inspection is not claimed.",
            "yuanzhifang scientific acceptance remains pending.",
        ],
        "notice": "audit.json is excluded from manifest.outputs to avoid a self-referential hash.",
    }
    (OUT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
