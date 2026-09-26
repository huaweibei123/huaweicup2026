"""One independent resource-window follow-up to the sealed zero-call wave batch."""
from pathlib import Path
import json

import wave_benchmark as base
from benchmark import artifact, git, relative

PARENT = "c42dbacf2b24d1075da8eda754e67749bb5d9f8f"
PRIOR_DATA = "05e83317f15dc5bf24b76aa51be376e705831867"
PRIOR = "results/a/q3-yuanzhifang/wave-20260925/manifest.json"
OUT = "results/a/q3-yuanzhifang/wave-followup-20260925"
RUN_ID = "yuanzhifang-q3-wave-followup-20260925"
ENTRY = "src/q3_yuanzhifang/wave_followup_benchmark.py"
_preflight = base.preflight


def preflight(graph_dir):
    identity = _preflight(graph_dir)
    path = "src/q3_yuanzhifang/wave_benchmark.py"
    if Path(path).read_bytes() != git("show", PARENT + ":" + path):
        raise ValueError("original frozen wave measurement changed")
    for path in (ENTRY, "docs/a/q3-yuanzhifang/WAVE_FOLLOWUP.md"):
        if Path(path).read_bytes() != git("show", identity["runner_commit"] + ":" + path):
            raise ValueError("follow-up runner/spec must be committed unchanged")
    if Path(PRIOR).read_bytes() != git("show", PRIOR_DATA + ":" + PRIOR):
        raise ValueError("sealed prior manifest identity mismatch")
    prior = json.loads(Path(PRIOR).read_bytes())
    if prior["status"] != "stopped" or any(prior["calls"].values()):
        raise ValueError("this follow-up requires the known zero-call resource stop")
    identity.update(runner_entry=dict(commit=identity["runner_commit"], **artifact(ENTRY)),
                    parent_runner=dict(commit=PARENT, **artifact("src/q3_yuanzhifang/wave_benchmark.py")),
                    prior_zero_call_batch=dict(commit=PRIOR_DATA, **artifact(PRIOR)))
    return identity


class Followup(base.WavePilot):
    def __init__(self, args):
        super().__init__(args)
        if args.output.as_posix() != OUT:
            raise ValueError("this independent batch has one fixed output directory")
        self.info.update(run_id=RUN_ID, runner_source_path=ENTRY,
                         prior_batch=dict(commit=PRIOR_DATA, path=PRIOR, calls=0))
        self.info["argv"][2] = relative(__file__)
        self.info["offline_costs"] += " Prior wave batch stopped before dispatch with zero solver/E0 calls; this is a separately frozen one-shot resource window."


def main():
    base.OUT = OUT
    base.WavePilot = Followup
    base.preflight = preflight
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
