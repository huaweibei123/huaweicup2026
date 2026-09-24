"""Analyze existing feedback evidence and draw quality/cost; zero evaluations."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("figures", type=Path)
    args = parser.parse_args()
    data = json.loads(args.batch.read_text())
    rows = []
    for item in data["records"]:
        candidates = item.get("solver_receipt", {}).get("candidates", [])
        seed = next((c.get("makespan") for c in candidates if c["name"] == "seed"), None)
        tree = next((c.get("makespan") for c in candidates if c["name"] == "tree"), None)
        tree_status = next((c["status"] for c in candidates if c["name"] == "tree"), "unobserved")
        chosen = item.get("makespan_cycles")
        if chosen is not None and seed is not None:
            assert chosen == min(seed, tree if tree is not None else seed)
        rows.append({"case": item["case_id"], "cores": item["cores"], "status": item["status"],
                     "tree_status": tree_status, "seed_cycles": seed, "tree_cycles": tree,
                     "chosen_cycles": chosen, "improvement_percent": 100 * (1 - chosen / seed)
                     if chosen is not None and seed else None,
                     "solver_wall_seconds": (item.get("solver_process") or {}).get("wall_seconds"),
                     "E0_calls": item["calls"]["E0"]})
    csv_path = args.batch.parent / "metrics.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    successful = [r for r in rows if r["status"] == "ok"]
    if successful:
        args.figures.mkdir(parents=True, exist_ok=True)
        plt.rcParams.update({"font.size": 10, "svg.hashsalt": "q3-feedback-v1"})
        fig, axes = plt.subplots(1, 2, figsize=(10, max(3.5, len(successful) * .38)),
                                 layout="constrained", sharey=True)
        labels = [f"{r['case']} / k={r['cores']}" for r in successful]
        quality = [r["seed_cycles"] / r["chosen_cycles"] for r in successful]
        wall = [r["solver_wall_seconds"] for r in successful]
        axes[0].barh(labels, quality, color="#256b8e", edgecolor="black", linewidth=.4)
        axes[0].axvline(1, color="#444444", linestyle="--", linewidth=1)
        axes[0].set(xlabel="Seed / selected Makespan (ratio)", xlim=(0, max(quality) * 1.2),
                    title="Official P3 quality")
        axes[1].barh(labels, wall, color="#b86a3c", edgecolor="black", linewidth=.4)
        axes[1].set(xlabel="Whole solver process wall (seconds)", xlim=(0, max(wall) * 1.2),
                    title="One observation on a shared host")
        for ax, values in zip(axes, [quality, wall]):
            for n, value in enumerate(values):
                ax.text(value + max(values) * .025, n, f"{value:.2f}", va="center", fontsize=9)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_axisbelow(True)
            ax.grid(axis="x", color="#dddddd", linewidth=.5)
        axes[0].invert_yaxis()
        outputs = {}
        for ext in ("png", "pdf", "svg"):
            path = args.figures / f"quality-cost.{ext}"
            fig.savefig(path, dpi=180)
            if ext == "svg":
                path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
            outputs[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        plt.close(fig)
        manifest = {"batch_sha256": hashlib.sha256(args.batch.read_bytes()).hexdigest(),
                    "metrics_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "outputs": outputs, "interpretation": "Ratio is matched in-process seed vs selected official Makespan; wall is whole new solver, no latency speedup or confidence interval claimed."}
        (args.figures / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"records": len(rows), "csv": str(csv_path), "evaluation_calls": 0}))


if __name__ == "__main__":
    main()
