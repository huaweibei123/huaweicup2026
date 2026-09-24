"""Canonical Python implementation of the exploratory native ranking kernel."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass


MAGIC = "NATIVE_PROXY_V1"
OUTPUT_HEADER = (
    "rank\tcandidate_id\tcompute_q6\ttransfer_q6\t"
    "communication_penalty_q6\timbalance_penalty_q6\tscore_q6\n"
)
U64_MAX = (1 << 64) - 1
ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+\Z", re.ASCII)


class ProtocolError(ValueError):
    """Input cannot be represented by the native kernel protocol."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    pipe_bound_q6: int
    dependency_bound_q6: int
    copy_bytes: int
    bandwidth: int
    cross_task_count: int
    cross_core_count: int
    imbalance_ppm: int


@dataclass(frozen=True)
class RankedCandidate:
    candidate_id: str
    compute_q6: int
    transfer_q6: int
    communication_penalty_q6: int
    imbalance_penalty_q6: int
    score_q6: int


def _parse_u64(text: str, field: str, line_number: int) -> int:
    if not text or not text.isascii() or not text.isdecimal():
        raise ProtocolError(f"line {line_number}: {field} must be decimal u64")
    value = int(text)
    if value > U64_MAX:
        raise ProtocolError(f"line {line_number}: {field} exceeds u64")
    return value


def _checked_add(left: int, right: int, label: str) -> int:
    value = left + right
    if value > U64_MAX:
        raise ProtocolError(f"overflow while computing {label}")
    return value


def _checked_mul(left: int, right: int, label: str) -> int:
    value = left * right
    if value > U64_MAX:
        raise ProtocolError(f"overflow while computing {label}")
    return value


def parse_input(raw: bytes) -> list[Candidate]:
    """Parse the strict ASCII protocol into validated candidates."""
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ProtocolError("input must be ASCII") from error
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    if not lines or lines[0] != MAGIC:
        raise ProtocolError(f"first line must be {MAGIC}")

    candidates: list[Candidate] = []
    seen: set[str] = set()
    fields = (
        "pipe_bound_q6",
        "dependency_bound_q6",
        "copy_bytes",
        "bandwidth",
        "cross_task_count",
        "cross_core_count",
        "imbalance_ppm",
    )
    for line_number, line in enumerate(lines[1:], start=2):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 8:
            raise ProtocolError(f"line {line_number}: expected 8 tab-separated fields")
        candidate_id = parts[0]
        if not ID_PATTERN.fullmatch(candidate_id):
            raise ProtocolError(f"line {line_number}: invalid candidate_id")
        if candidate_id in seen:
            raise ProtocolError(f"line {line_number}: duplicate candidate_id")
        values = [
            _parse_u64(value, field, line_number)
            for field, value in zip(fields, parts[1:])
        ]
        candidate = Candidate(candidate_id, *values)
        if candidate.bandwidth == 0:
            raise ProtocolError(f"line {line_number}: bandwidth must be positive")
        if candidate.cross_core_count > candidate.cross_task_count:
            raise ProtocolError(
                f"line {line_number}: cross_core_count exceeds cross_task_count"
            )
        seen.add(candidate_id)
        candidates.append(candidate)
    if not candidates:
        raise ProtocolError("input must contain at least one candidate")
    return candidates


def score(candidate: Candidate) -> RankedCandidate:
    """Compute one fixed-point score using the language-neutral formula."""
    compute_q6 = max(candidate.pipe_bound_q6, candidate.dependency_bound_q6)
    transfer_numerator = _checked_mul(candidate.copy_bytes, 1_000_000, "transfer")
    transfer_q6 = transfer_numerator // candidate.bandwidth
    if transfer_numerator % candidate.bandwidth:
        transfer_q6 = _checked_add(transfer_q6, 1, "transfer ceiling")
    task_penalty = _checked_mul(candidate.cross_task_count, 25_000, "task penalty")
    core_penalty = _checked_mul(candidate.cross_core_count, 225_000, "core penalty")
    communication_penalty_q6 = _checked_add(
        task_penalty, core_penalty, "communication penalty"
    )
    imbalance_penalty_q6 = max(candidate.imbalance_ppm - 1_000_000, 0)
    score_q6 = compute_q6
    score_q6 = _checked_add(score_q6, transfer_q6, "score")
    score_q6 = _checked_add(score_q6, communication_penalty_q6, "score")
    score_q6 = _checked_add(score_q6, imbalance_penalty_q6, "score")
    return RankedCandidate(
        candidate.candidate_id,
        compute_q6,
        transfer_q6,
        communication_penalty_q6,
        imbalance_penalty_q6,
        score_q6,
    )


def evaluate_bytes(raw: bytes) -> bytes:
    """Evaluate and serialize canonical ranked TSV bytes."""
    ranked = sorted(
        (score(candidate) for candidate in parse_input(raw)),
        key=lambda item: (item.score_q6, item.candidate_id),
    )
    rows = [OUTPUT_HEADER]
    for rank, item in enumerate(ranked, start=1):
        rows.append(
            f"{rank}\t{item.candidate_id}\t{item.compute_q6}\t{item.transfer_q6}\t"
            f"{item.communication_penalty_q6}\t{item.imbalance_penalty_q6}\t"
            f"{item.score_q6}\n"
        )
    return "".join(rows).encode("ascii")


def main() -> int:
    try:
        result = evaluate_bytes(sys.stdin.buffer.read())
    except ProtocolError as error:
        print(f"protocol error: {error}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
