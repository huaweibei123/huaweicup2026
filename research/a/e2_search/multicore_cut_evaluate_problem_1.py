"""Official-format full diagnostics: transparently route the entire call to E1.

Run as a module from the repository root. This route has no native speed claim.
Metadata goes to stderr rather than modifying the official result/Trace schema.
"""
import sys
from src.eval_exact.cli import main

if __name__ == "__main__":
    print("[E2 ROUTE] E1 full diagnostics; native search scorer not used", file=sys.stderr)
    raise SystemExit(main())
