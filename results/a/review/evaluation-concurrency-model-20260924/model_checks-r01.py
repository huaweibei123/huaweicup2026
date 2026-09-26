"""Executable design checks, NOT a worker service or evaluator benchmark.

Only standard-library discrete events and an in-memory accounting model. The
integer durations/memory weights below are invented fixtures, never measurements.
No evaluator imports, subprocesses, sleeps, network, or background service.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys
import time


@dataclass(frozen=True)
class Job:
    candidate_id: str
    tenant: str
    ticks: int
    memory_units: int = 1


def schedule(jobs, *, workers, policy, memory_units=None, caps=None):
    """Unit-CPU non-preemptive events; all fixture jobs arrive at tick zero.

    fair = one dispatch opportunity per ready tenant, skipping a tenant that
    cannot currently fit. This verifies bounded count/memory, not CPU-time fair
    shares, dynamic admission, queue byte limits, or OS enforcement.
    """
    assert workers > 0 and policy in {"fair", "fifo"}
    assert len({job.candidate_id for job in jobs}) == len(jobs)
    budget = workers if memory_units is None else memory_units
    assert all(job.ticks > 0 and 0 < job.memory_units <= budget for job in jobs)
    tenants = list(dict.fromkeys(job.tenant for job in jobs))
    limits = caps or {tenant: workers for tenant in tenants}
    assert all(limits.get(tenant, 0) > 0 for tenant in tenants)
    remaining, active, records = list(jobs), [], []
    ring = deque(tenants)
    now, peak_workers, peak_memory = 0, 0, 0
    while remaining or active:
        while len(active) < workers:
            in_use = Counter(job.tenant for _, job in active)
            used_memory = sum(job.memory_units for _, job in active)

            def eligible(job):
                return (in_use[job.tenant] < limits[job.tenant]
                        and used_memory + job.memory_units <= budget)

            chosen = None
            if policy == "fifo":
                chosen = next((job for job in remaining if eligible(job)), None)
            else:
                for _ in range(len(ring)):
                    tenant = ring[0]
                    ring.rotate(-1)
                    # Head of each tenant queue; do not bypass its order.
                    first = next((job for job in remaining if job.tenant == tenant), None)
                    if first is not None and eligible(first):
                        chosen = first
                        break
            if chosen is None:
                break
            remaining.remove(chosen)
            active.append((now + chosen.ticks, chosen))
            records.append({"candidate_id": chosen.candidate_id, "tenant": chosen.tenant,
                            "start_tick": now, "finish_tick": now + chosen.ticks,
                            "delivered_tick": now + chosen.ticks})
            peak_workers = max(peak_workers, len(active))
            peak_memory = max(peak_memory, sum(job.memory_units for _, job in active))
            assert len(active) <= workers and peak_memory <= budget
        if active:
            now = min(finish for finish, _ in active)
            active = [(finish, job) for finish, job in active if finish != now]
        elif remaining:
            raise AssertionError("fixture is unschedulable")
    return dict(makespan_ticks=now, peak_workers=peak_workers,
                peak_memory_units=peak_memory, records=records)


def barrier(jobs, workers):
    """Existing pool's worker-sized barrier shape, equal memory/CPU jobs only."""
    assert workers > 0 and all(job.memory_units == 1 for job in jobs)
    now, records = 0, []
    for offset in range(0, len(jobs), workers):
        chunk = jobs[offset:offset + workers]
        end = now + max(job.ticks for job in chunk)
        records.extend(dict(candidate_id=job.candidate_id, tenant=job.tenant,
                            start_tick=now, finish_tick=now + job.ticks,
                            delivered_tick=end) for job in chunk)
        now = end
    return dict(makespan_ticks=now, records=records)


class LedgerModel:
    """In-memory oracle reservation and identity state machine only.

    A valid native terminal proof returns a reservation; crash/started timeout
    holds it. This has NO persistence/transactions/process cleanup implementation.
    """
    def __init__(self, oracle_limit, outstanding_limit=8):
        self.oracle_limit = oracle_limit
        self.outstanding_limit = outstanding_limit
        self.records = {}

    def available(self):
        return self.oracle_limit - sum(row["held"] + row["used"]
                                       for row in self.records.values())

    def submit(self, operation_id, identity, *, possible_e0=1):
        assert possible_e0 in (0, 1)
        if operation_id in self.records:
            row = self.records[operation_id]
            if row["identity"] != identity or row["possible_e0"] != possible_e0:
                raise ValueError("identity_conflict")
            return row["state"]
        outstanding = sum(row["state"] in {"queued", "started"}
                          for row in self.records.values())
        if outstanding >= self.outstanding_limit:
            return "backpressure"
        if possible_e0 > self.available():
            return "budget_exhausted"
        self.records[operation_id] = dict(identity=identity, possible_e0=possible_e0,
                                         state="queued", held=possible_e0, used=0)
        return "queued"

    def start(self, operation_id):
        row = self.records[operation_id]
        if row["state"] != "queued":
            raise ValueError("not_queued")
        row["state"] = "started"

    def cancel(self, operation_id):
        row = self.records[operation_id]
        if row["state"] == "queued":
            row.update(state="cancelled_before_start", held=0)
            return True
        return False  # no refund for a started or unknown execution

    def finish(self, operation_id, outcome):
        row = self.records[operation_id]
        if row["state"] != "started":
            raise ValueError("not_started")
        if outcome == "native_confirmed":
            row.update(state="completed", held=0)
        elif outcome in {"e0_completed", "official_rejected"}:
            if row["possible_e0"] != 1:
                raise ValueError("unreserved_oracle")
            row.update(state="completed", held=0, used=1)
        elif outcome in {"crash", "timeout", "lost_receipt"}:
            row["state"] = "unknown_cost"
        else:
            raise ValueError("unknown_outcome")
        assert self.available() >= 0


def run_checks():
    checks = []

    def passed(name):
        checks.append(name)

    skew = [Job("slow", "a", 100)] + [Job(f"short-{i}", "a", 1) for i in range(1, 9)]
    blocked = barrier(skew, 2)
    rolling = schedule(skew, workers=2, policy="fair")
    assert blocked["makespan_ticks"] == 104 and rolling["makespan_ticks"] == 100
    assert blocked["records"][1]["delivered_tick"] == 100
    assert rolling["records"][1]["delivered_tick"] == 1
    assert rolling["records"][2]["start_tick"] == 1
    passed("slow_candidate_does_not_hold_completed_result_or_next_dispatch")

    mixed = ([Job(f"a-{i}", "a", 8) for i in range(9)]
             + [Job(f"b-{i}", "b", 2) for i in range(3)] + [Job("c-0", "c", 1)])
    fifo = schedule(mixed, workers=3, policy="fifo")
    fair = schedule(mixed, workers=3, policy="fair")
    c_fifo = next(row for row in fifo["records"] if row["candidate_id"] == "c-0")
    c_fair = next(row for row in fair["records"] if row["candidate_id"] == "c-0")
    assert c_fifo["delivered_tick"] == 27 and c_fair["delivered_tick"] == 1
    assert {row["tenant"] for row in fair["records"][:3]} == {"a", "b", "c"}
    assert sorted(row["candidate_id"] for row in fair["records"]) == sorted(job.candidate_id for job in mixed)
    passed("three_tenants_share_dispatch_without_fifo_queue_starvation")

    resources = [Job("large", "a", 7, 3), Job("a2", "a", 1),
                 Job("b", "b", 2, 2), Job("c", "c", 1)]
    limited = schedule(resources, workers=3, memory_units=4, policy="fair",
                       caps={"a": 1, "b": 1, "c": 1})
    assert limited["peak_memory_units"] <= 4 and limited["peak_workers"] <= 3
    by_id = {row["candidate_id"]: row for row in limited["records"]}
    assert by_id["a2"]["start_tick"] >= by_id["large"]["finish_tick"]
    assert by_id["b"]["start_tick"] >= by_id["large"]["finish_tick"]
    passed("simulated_global_memory_and_per_tenant_inflight_caps_hold")

    ledger = LedgerModel(1)
    assert ledger.submit("op1", "p3-graph-plan-config-engine") == "queued"
    assert ledger.submit("op1", "p3-graph-plan-config-engine") == "queued"
    assert ledger.available() == 0 and len(ledger.records) == 1
    try:
        ledger.submit("op1", "different-plan")
    except ValueError as error:
        assert str(error) == "identity_conflict"
    else:
        raise AssertionError("conflicting identity accepted")
    assert ledger.submit("op2", "other-plan") == "budget_exhausted"
    assert ledger.cancel("op1") and ledger.available() == 1
    passed("idempotent_submit_conflict_and_prestart_cancel_preserve_budget")

    assert ledger.submit("op2", "other-plan") == "queued"
    ledger.start("op2")
    assert not ledger.cancel("op2") and ledger.available() == 0
    ledger.finish("op2", "timeout")
    assert ledger.submit("op2", "other-plan") == "unknown_cost"
    assert ledger.submit("op3", "new-plan") == "budget_exhausted"
    assert ledger.records["op2"]["held"] == 1 and ledger.available() == 0
    passed("started_timeout_keeps_oracle_reservation_and_does_not_retry")

    settled = LedgerModel(1)
    settled.submit("n", "native")
    settled.start("n")
    settled.finish("n", "native_confirmed")
    assert settled.available() == 1
    settled.submit("o", "fallback")
    settled.start("o")
    settled.finish("o", "official_rejected")
    assert settled.available() == 0 and settled.records["o"]["used"] == 1
    passed("native_proof_releases_reservation_but_official_rejection_costs_one")

    queue = LedgerModel(2, outstanding_limit=1)
    queue.submit("first", "one")
    assert queue.submit("second", "two") == "backpressure"
    assert len(queue.records) == 1 and queue.available() == 1
    zero = LedgerModel(0)
    assert zero.submit("unsafe", "automatic-fallback") == "budget_exhausted"
    passed("backpressure_has_no_cost_and_zero_budget_blocks_automatic_fallback")

    # Wire delivery can reorder; selection uses a frozen candidate set and ID tie-break.
    score_rows = [("x", 10), ("a", 10), ("b", 12)]
    decide = lambda rows: min(rows, key=lambda item: (item[1], item[0]))[0]
    assert decide(score_rows) == decide(list(reversed(score_rows))) == "a"
    current_epoch = 2
    received = [dict(epoch=1, candidate_id="old", score=1),
                dict(epoch=2, candidate_id="new", score=10)]
    eligible = [row for row in received if row["epoch"] == current_epoch]
    assert len(received) == 2 and eligible[0]["candidate_id"] == "new"
    pairs = {"pair0": {2: "completed"}}
    assert set(pairs["pair0"]) != {2, 3}
    passed("fixed_round_ties_late_epochs_and_incomplete_pairs_are_explicit")

    return {
        "kind": "synthetic_control_plane_model_only",
        "evaluations": {"E0": 0, "E1": 0, "E2": 0},
        "real_workers_started": 0,
        "units": "invented_integer_ticks_and_memory_units_not_seconds_or_bytes",
        "checks_passed": checks,
        "fixtures": {"skew": [asdict(job) for job in skew],
                     "mixed": [asdict(job) for job in mixed],
                     "resource": [asdict(job) for job in resources]},
        "results": {"barrier": blocked, "rolling": rolling,
                    "fifo_mixed": fifo, "fair_mixed": fair, "resource_model": limited},
        "limitations": ["No real evaluation or speedup claim", "No worker/IPC/OS tests",
                        "No persistence, concurrent transactions or restart recovery",
                        "Round robin is dispatch fairness, not CPU-time fairness",
                        "All fixture jobs arrive at tick zero; no dynamic admission"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    result = run_checks()
    result.update(python_version=platform.python_version(), platform=platform.platform(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  model_check_wall_seconds=time.perf_counter() - start,
                  command="python research/a/evaluation_service/model_checks.py --output <new-output.json>")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite another run's evidence.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"checks_passed": len(result["checks_passed"]),
                      "evaluations": result["evaluations"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
