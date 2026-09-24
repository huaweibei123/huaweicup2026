"""Official CLI compatibility route to the matching E0."""
import os
import sys
from src.eval_exact._official import OFFICIAL_CODE_DIR, verify_official_code


def main(problem):
    if problem not in (2,3):
        raise ValueError('problem must be 2 or 3')
    verify_official_code()
    print(f'[E2 ROUTE] P{problem} E0 full diagnostics; native search scorer not used',file=sys.stderr,flush=True)
    path = OFFICIAL_CODE_DIR/f'multicore_cut_evaluate_problem_{problem}.py'
    if os.name == 'nt':
        import subprocess

        # Windows exec starts a successor; keep this wrapper alive to wait for it.
        completed = subprocess.run(
            [sys.executable,str(path),*sys.argv[1:]], shell=False, check=False,
        )
        # The P2/P3 module entry points call main directly, so exit here.
        raise SystemExit(completed.returncode)
    # Replace this process so normal CLI exit/signal handling is retained.
    os.execv(sys.executable,[sys.executable,str(path),*sys.argv[1:]])
