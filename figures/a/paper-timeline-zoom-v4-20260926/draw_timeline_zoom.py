#!/usr/bin/env python3
"""Render v7 timeline readability candidates from frozen official event JSON only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parent
PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")
SHORT = ("M", "V", "MTE2", "MTE3")
COLORS = ("#24517a", "#765398", "#138177", "#b66a2e")
INK = "#162639"

CONFIG = {
    "p26": dict(file="p1-026-k5", keys=("old", "new"), labels=("原切分", "分支重新分配"),
                xmax=44114, window=(5200, 9400), cores=(0, 1), expected=(44114, 42014),
                sha256="9d7eb4298f5c97aebea3c9699630604f8a2b62211216d7879a8c24ee8f290151"),
    "p38": dict(file="p2-019-k5", keys=("control", "c04"), labels=("主算法", "C04"),
                xmax=28514, window=(13800, 17400), cores=(0, 3), expected=(16247, 28514),
                sha256="8b1ebb9e3a116df56dbf89e8977b669411675734968a61b5c009ad8c2a6acd1f"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def setup_style(v7_source: Path) -> None:
    font_dir = v7_source.parent / "fonts"
    for name in ("SimSun.ttf", "Times.TTF", "Timesbd.TTF"):
        if (font_dir / name).exists():
            font_manager.fontManager.addfont(font_dir / name)
    plt.rcParams.update({
        "font.family": ["Times New Roman", "SimSun", "DejaVu Sans"],
        "font.size": 7.2, "axes.labelsize": 7.2, "xtick.labelsize": 6.8,
        "ytick.labelsize": 6.7, "axes.unicode_minus": False,
        "pdf.fonttype": 42, "svg.fonttype": "none",
        "axes.spines.top": False, "axes.spines.right": False,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })


def bands(ax, d, cores, xlim, zoom=False, selected=None):
    """Draw each recorded Task and operation exactly once; x values stay in cycles."""
    lanes = []
    for core_id in cores:
        lanes.append((core_id, "Task", None))
        lanes.extend((core_id, short, pipe) for short, pipe in zip(SHORT, PIPES))
    labels = []
    core_map = {c["core_id"]: c for c in d["per_core_timeline"]}
    for i, (core_id, kind, pipe) in enumerate(lanes):
        y = len(lanes) - 1 - i
        c = core_map[core_id]
        labels.append(f"{core_id}·{kind}")
        ax.axhline(y - .48, color="#e3e9ed", lw=.35, zorder=0)
        if kind == "Task":
            events = c["tasks"]
            for t in events:
                ax.add_patch(Rectangle((t["start"], y-.32), t["duration"], .64,
                                       facecolor="#dbe6ef", edgecolor=INK, lw=.55,
                                       clip_on=True, zorder=2))
                left, right = max(t["start"], xlim[0]), min(t["end"], xlim[1])
                if right-left >= (xlim[1]-xlim[0]) * (.037 if zoom else .050):
                    ax.text((left+right)/2, y, f'T{t["task_id"]}',
                            ha="center", va="center", fontsize=6.2 if zoom else 6.5,
                            color=INK, clip_on=True, zorder=3)
        else:
            color = COLORS[PIPES.index(pipe)]
            for o in c["ops"]:
                if o["pipe"] == pipe:
                    ax.add_patch(Rectangle((o["start"], y-.27), o["duration"], .54,
                                           facecolor=color, edgecolor="none", clip_on=True,
                                           zorder=2))
    ax.set_ylim(-.55, len(lanes)-.45)
    ax.set_xlim(*xlim)
    ax.set_yticks(list(range(len(lanes)-1, -1, -1)), labels)
    ax.tick_params(axis="y", length=0, pad=3)
    ax.grid(axis="x", color="#dce3e9", lw=.45, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("时间 / cycle")
    if zoom:
        ax.set_xticks(list(range((xlim[0]+499)//500*500, xlim[1]+1, 1000)))
    else:
        ax.set_xticks(list(range(0, xlim[1]+1, 5000 if xlim[1]<30000 else 10000)))
        ax.axvline(d["makespan"], color=INK, lw=.85, ls="--", zorder=4)
        w0, w1 = selected
        ax.axvspan(w0, w1, facecolor="#f5d69b", alpha=.25, edgecolor="#9b6826", lw=.75,
                   zorder=1)


def zoom_evidence(d, cores, window):
    lo, hi = window
    entries = []
    for c in d["per_core_timeline"]:
        if c["core_id"] not in cores:
            continue
        for t in c["tasks"]:
            if t["start"] < hi and t["end"] > lo:
                entries.append(dict(core=c["core_id"], task_id=t["task_id"],
                                    subgraph_id=t.get("subgraph_id"),
                                    task_start=t["start"], task_end=t["end"],
                                    overlapping_ops=sum(o["start"] < hi and o["end"] > lo
                                                        for o in c["ops"] if o["task_id"] == t["task_id"])))
    return entries


def save_panel(fig, stem):
    fig.savefig(OUT/(stem+".pdf"), metadata={"Creator":"v7 frozen event renderer","CreationDate":None})
    svg = OUT/(stem+".svg")
    fig.savefig(svg, metadata={"Date":None})
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines())+"\n")
    fig.savefig(OUT/(stem+".png"), dpi=300)
    fig.savefig(OUT/(stem+"-160mm-preview.png"), dpi=300)
    plt.close(fig)


def render(which, v7_source):
    cfg = CONFIG[which]
    relpath = Path("data/figure-inputs") / (cfg["file"] + ".json.gz")
    path = v7_source / relpath
    raw = path.read_bytes()
    assert sha(raw) == cfg["sha256"], f"frozen input hash changed: {path}"
    data = json.loads(gzip.decompress(raw))
    results = [data[k]["result"] for k in cfg["keys"]]
    assert tuple(d["makespan"] for d in results) == cfg["expected"]
    assert all(d["num_cores"] == 5 for d in results)
    audit = {"source_relpath_from_v7_source": relpath.as_posix(),
             "source_sha256": sha(raw), "case_id": data["case_id"],
             "x_axis_unit": "cycle", "shared_full_axis_cycles": [0, cfg["xmax"]],
             "zoom_window_cycles": list(cfg["window"]), "zoom_cores": list(cfg["cores"]),
             "panels": {"full": {"width_mm":160,"height_mm":170,"all_cores":True},
                        "zoom": {"width_mm":160,"height_mm":92,"selected_cores":list(cfg["cores"])}},
             "source_semantics": "per_core_timeline.tasks = Task spans; per_core_timeline.ops = recorded Pipe occupancy events; blank lane has no recorded occupancy and is not assigned a cause",
             "schemes": []}
    for key, d in zip(cfg["keys"], results):
        tasks = [t for c in d["per_core_timeline"] for t in c["tasks"]]
        ops = [o for c in d["per_core_timeline"] for o in c["ops"]]
        assert all(0 <= x["start"] < x["end"] <= cfg["xmax"] and
                   x["end"]-x["start"] == x["duration"] for x in tasks+ops)
        assert all(o["pipe"] in PIPES for o in ops)
        audit["schemes"].append(dict(key=key, makespan_cycles=d["makespan"],
             added_copy_bytes=d["data_movement_bytes"]["added_copy_bytes"],
             task_count=len(tasks), op_count=len(ops),
             ops_by_pipe={p:sum(o["pipe"] == p for o in ops) for p in PIPES},
             zoom_tasks=zoom_evidence(d, cfg["cores"], cfg["window"])))

    fig = plt.figure(figsize=(160/25.4, 170/25.4), constrained_layout=False)
    gs = fig.add_gridspec(2, 1, left=.14, right=.985, top=.965, bottom=.065, hspace=.35)
    axes = [fig.add_subplot(gs[i]) for i in range(2)]
    for i, (ax, d, label) in enumerate(zip(axes, results, cfg["labels"])):
        bands(ax, d, range(5), (0,cfg["xmax"]), selected=cfg["window"])
        ax.set_title(f"({chr(97+i)}) {label}  ·  完成时间 {d['makespan']:,} cycle", loc="left",
                     fontsize=8.2, fontweight="bold", pad=5)
    save_panel(fig, f"{which}-timeline-full")

    fig = plt.figure(figsize=(160/25.4, 92/25.4), constrained_layout=False)
    gs = fig.add_gridspec(2, 1, left=.14, right=.985, top=.96, bottom=.12, hspace=.55)
    axes = [fig.add_subplot(gs[i]) for i in range(2)]
    for i, (ax,d) in enumerate(zip(axes,results)):
        bands(ax, d, cfg["cores"], cfg["window"], zoom=True)
        ev = audit["schemes"][i]["zoom_tasks"]
        ids = ", ".join(f"C{e['core']}:T{e['task_id']}" +
                        (f"/SG{e['subgraph_id']}" if e["subgraph_id"] is not None else "") for e in ev)
        ax.set_title(f"({chr(97+i)}) 局部放大 {cfg['window'][0]:,}–{cfg['window'][1]:,} cycle  ·  {ids}",
                     loc="left", fontsize=7.1, pad=4)
    save_panel(fig, f"{which}-timeline-zoom")
    (OUT/(f"{which}-timeline-semantic.json")).write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=("p26","p38","all"), default="all", nargs="?")
    parser.add_argument("--v7-source", type=Path, required=True,
                        help="Frozen v7/source directory containing data/figure-inputs")
    args = parser.parse_args()
    setup_style(args.v7_source)
    for which in (CONFIG if args.which == "all" else (args.which,)):
        render(which, args.v7_source)
