"""Read two archived 044/k5 P3 results; verify cache saturation without E0."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "28e8c7ddfe2223b2261056f554259c43d5bba272"
BASE = "results/a/q3-nikolastarx/"


def main():
    sources = []

    def read(path):
        blob = subprocess.run(["git", "show", f"{SOURCE}:{path}"], cwd=ROOT,
                              check=True, capture_output=True).stdout
        sources.append(dict(path=path, bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest()))
        return blob

    published = json.loads(read(BASE + "prefix-cache-critical-audit-20260925/summary.json"))
    path_audit = json.loads(read(BASE + "prefix-realized-path-20260925/audit.json"))
    paths = {
        "prefix": BASE + "pipeline-prefix-linux-20260925/receipt-public/artifacts/044-result.json.gz",
        "capacity": BASE + "pipeline-capacity-two-shot-20260925/evaluation/044/result.json.gz",
    }
    summaries, transfers, movements = {}, {}, {}
    for name, path in paths.items():
        raw = read(path)
        assert sources[-1]["sha256"] == published["source_sha256"][path]
        result = json.loads(gzip.decompress(raw))
        assert (result["scene"], result["problem"], result["num_cores"], result["cache_mode"]) == ("B", 3, 5, "read_only")
        assert result["cache_capacity_bytes"] == 1048576
        assert result["bandwidth_bytes_per_cycle"] == 60
        assert result["cache_bandwidth_bytes_per_cycle"] == 250
        assert result["cross_core_copy_delay_cycles"] == 500
        accesses = defaultdict(list)
        inserts = []
        for event in result["cache_events"]:
            if event["event"] in ("hit", "miss"):
                accesses[event["tensor_id"]].append(event)
            elif event["event"] == "insert":
                inserts.append(event)
            else:
                raise ValueError("Unexpected event")
        counter = Counter()
        for key, events in accesses.items():
            assert len({e["size_bytes"] for e in events}) == 1
            assert all(a["time"] <= b["time"] for a, b in zip(events, events[1:]))
            assert events[0]["event"] == "miss"
            counter[key, events[0]["size_bytes"]] = len(events)
        hit = sum(e["size_bytes"] for seq in accesses.values() for e in seq if e["event"] == "hit")
        miss = sum(e["size_bytes"] for seq in accesses.values() for e in seq if e["event"] == "miss")
        unique = sum(size for _, size in counter)
        upper = sum((count - 1) * size for (_, size), count in counter.items())
        repeat_misses = sum(e["event"] == "miss" for seq in accesses.values() for e in seq[1:])
        evictions = sum(len(e["evicted_tensor_ids"]) for e in inserts)
        assert hit == result["cache_stats"]["hit_bytes"] == upper
        assert miss == result["cache_stats"]["miss_bytes"] == unique
        assert repeat_misses == evictions == 0
        assert unique <= result["cache_capacity_bytes"]
        assert len(inserts) == len(accesses)
        assert len({e["tensor_id"] for e in inserts}) == len(accesses)
        assert hit + miss == sum(count * size for (_, size), count in counter.items())
        assert result["makespan"] == published[name]["makespan_cycles"]
        summaries[name] = dict(
            makespan_cycles=result["makespan"], access_count=sum(counter.values()),
            distinct_keys=len(counter), distinct_key_bytes=unique,
            hit_bytes=hit, miss_bytes=miss, theoretical_fixed_multiset_hit_upper_bytes=upper,
            fixed_multiset_hit_upper_achieved=True, byte_hit_rate=hit / (hit + miss),
            repeated_key_misses=repeat_misses, evicted_keys=evictions,
            unused_capacity_bytes=result["cache_capacity_bytes"] - unique)
        transfers[name] = counter
        movements[name] = result["data_movement_bytes"]
    assert transfers["prefix"] == transfers["capacity"]
    assert movements["prefix"] == movements["capacity"]
    assert summaries["capacity"]["makespan_cycles"] - summaries["prefix"]["makespan_cycles"] == 366
    plan = read(BASE + "pipeline-prefix-linux-20260925/receipt-public/artifacts/case_044_multicore_res.json")
    assert sources[-1]["sha256"] == path_audit["plan_sha256"]
    assert set(json.loads(plan)) == {"node_to_subgraph", "core_schedules"}
    assert path_audit["official_result_sha256"] == published["source_sha256"][paths["prefix"]]
    # These are checks of the published path audit, not a reconstruction of its
    # 1678-node prepared graph. Preserve that distinction in the output.
    parts = path_audit["realized_path_contributions"]
    assert sum(v for k, v in parts.items() if k != "duration_excess_above_minimum") == 38024
    assert 38024 - path_audit["prepared_graph_lower_bound"] == parts["duration_excess_above_minimum"] == 8244
    for core, prefix in path_audit["cold_prefixes"].items():
        floor = prefix["work"] + sum(
            min(other["work"], max(0, prefix["work"] - (len(other["ops"]) - 1)))
            for key, other in path_audit["cold_prefixes"].items() if key != core)
        assert floor == prefix["finish_lower_bound"] <= prefix["official_finish"]
    output = dict(
        schema="p3-prefix-cache-paper-audit-v1", source_commit=SOURCE,
        source_files=sources, raw_result_checks=summaries,
        same_transfer_key_size_multiplicities=True, same_data_movement_fields=True,
        data_movement_bytes=movements["prefix"], plan_sha256=path_audit["plan_sha256"],
        published_path_audit_checks=dict(
            source_is_same_plan_and_result=True, contribution_sum_cycles=38024,
            excess_over_optimistic_cycles=8244, corrected_prefix_floor_arithmetic=True,
            conditional_model_lower_bound=path_audit["rounded_sharing_model_lower_bound"],
            independently_reconstructed_prepared_graph=False),
        calls=dict(solver=0, prepare=0, Step=0, E0=0, E1=0, E2=0),
        limits=["Two fixed P3 compressed results and one plan were independently hashed and read here.",
                "Cache event/key/multiplicity arithmetic was recomputed; no same-plan P2 exists in this audit.",
                "Critical-path graph and all-start-times equality remain attributed to the published team audit.",
                "36592 is a conditional rational shared-service model bound, not an official floating-point pruning certificate."])
    target = ROOT / "paper/drafts/p3-prefix-cache-audit.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=target.relative_to(ROOT).as_posix(), raw_results=summaries,
                          checks=output["published_path_audit_checks"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
