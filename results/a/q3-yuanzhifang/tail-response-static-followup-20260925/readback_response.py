"""Read stored response coefficients and receipts; never construct or evaluate a graph."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path


def readback(directory):
    record_bytes = (directory / "run.json").read_bytes()
    record = json.loads(record_bytes)
    byte_checks = {}
    for name in ("stdout.json.gz", "stderr.txt.gz"):
        packed = (directory / name).read_bytes()
        raw = gzip.decompress(packed)
        byte_checks[name] = dict(gzip_sha256=hashlib.sha256(packed).hexdigest(),
                                raw_sha256=hashlib.sha256(raw).hexdigest())
        for field, value in byte_checks[name].items():
            if value != record[name][field]:
                raise ValueError("stored byte identity mismatch: " + name)
    result = json.loads(gzip.decompress((directory / "stdout.json.gz").read_bytes()))
    if record["status"] != "ok" or not all(result["checks"].values()) or not all(record["expected_comparison"].values()):
        raise ValueError("stored analysis did not pass")
    coefficients = result["response"]["coeffs"]
    arrival = result["response"]["arrival"]
    bound = result["response"]["bound"]
    peak = 0
    next_arrival = 0
    rows = []
    for c, (x, reported_arrival) in enumerate(zip(coefficients, arrival)):
        if reported_arrival != next_arrival:
            raise ValueError("inconsistent reported arrival")
        finish = max(x["A"], next_arrival + x["B"])
        tail_finish = max(x["C"], next_arrival + x["D"])
        if finish != result["oracle"]["core_finish"][c] or tail_finish != result["oracle"]["tail_finish"][c]:
            raise ValueError("coefficient composition differs from stored full-DAG oracle")
        rows.append(dict(core=c, arrival=next_arrival, **{k: x[k] for k in "ABCD"},
                         finish=finish, tail_finish=tail_finish,
                         local_incoming_delay_slack=x["A"] - next_arrival - x["B"]))
        peak = max(peak, finish)
        next_arrival = tail_finish
    if peak != bound:
        raise ValueError("composed global bound mismatch")
    # G_c(R)=max(P_c,R+Q_c) is the worst completion over the entire suffix.
    suffix_P = suffix_Q = None
    for c in range(len(rows)-1, -1, -1):
        x = rows[c]
        if suffix_P is None:
            suffix_P, suffix_Q = x["A"], x["B"]
        else:
            suffix_P, suffix_Q = (max(x["A"], suffix_P, x["C"] + suffix_Q),
                                  max(x["B"], x["D"] + suffix_Q))
        x.update(suffix_P=suffix_P, suffix_Q=suffix_Q,
                 single_gate_delay_to_fixed_global_bound=bound-x["arrival"]-suffix_Q)
    return dict(schema="q3-response-root-readback-v1", generated_at_utc=datetime.now(timezone.utc).isoformat(),
                run_sha256=hashlib.sha256(record_bytes).hexdigest(), byte_checks=byte_checks,
                recomposed_bound=peak, rows=rows,
                all_current_arrivals_locally_hidden=all(x["local_incoming_delay_slack"] >= 0 for x in rows),
                input_scope="Stored receipts and four-coefficient arithmetic only; no original graph/model/Step/E0 execution.",
                limitation="Delay tolerances apply only to one incoming gate in the fixed zero-COPY response chain. They are not a simultaneous per-boundary budget or proof about official COPY, spill, Cache, or transfer lag.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = readback(Path(__file__).resolve().parent)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        print(text, end="")
