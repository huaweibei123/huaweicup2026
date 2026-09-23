"""Generate one proposal in a cancellable process; never invokes an evaluator."""
import argparse
import json
from pathlib import Path
from .proposals import GraphIndex, propose


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--graph', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--method', choices=['M1', 'M2'], required=True)
    p.add_argument('--spec', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    index = GraphIndex(json.loads(a.graph.read_text(encoding='utf-8')))
    plan = propose(index, a.method, json.loads(a.spec), json.loads(a.baseline.read_text(encoding='utf-8')))
    with a.output.open('x', encoding='utf-8') as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'eligible_ops': len(index.ops), 'subgraphs': sum(map(len, plan['core_schedules']))}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        known = ('packet contraction creates a cycle', 'contracted subgraph graph contains a cycle',
                 'dependency order violation on core')
        rejected = any(marker in str(error) for marker in known)
        print(json.dumps({'status':'construction_rejected' if rejected else 'generator_error','error':str(error)}))
        raise SystemExit(2 if rejected else 1)
