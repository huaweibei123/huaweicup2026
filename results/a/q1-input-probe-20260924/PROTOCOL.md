# P1 external-input-window one-cell probe

1. **Goal:** test actual E0 quality of external-input depth windows on044/k4; do not infer improvement from input-byte proxies or fewer spill bytes alone.
2. **Input:** frozen official graph/config/code; algorithm `src/q1/input_windows.py` at `d438d380326d9cfa3d38097f5ab60d35aa6e5df4`. Explicit parameters input_budget_bytes262144, activation_bytes524288, max_phases32. Inherited bounded04 unchanged.
3. **Output:** independent run, raw complete plan/result/trace/log and receipts, board-v1 feed/precheck. Reuse exact previous bounded044/fixed64/official singlecore result originals at their fixed source SHAs; no rerun.
4. **Limits:** separate explicit parent authorization from the048/071 sink probe. This run at most1 solver+1 E0, solver30s/E060s, total120s, one worker; no retry/E1/E2/Colab. Both runs execute sequentially only after parent's resource window, never overlap. At least4GiB free+inactive+speculative proxy at dispatch. Shared host, descriptive wall time, not a controlled speed ratio.
5. **Acceptance:** source/hash verification, exact official plan interface, positive official Makespan, complete original bytes and board precheck; preserve regression/failure. Explicitly distinguish online construction wall and independent E0 wall. Bounded04 fallback construction is included in the one complete solver process/time.
6. **End:** stop after the single attempted cell and export; no extra candidates. Return fixed commits to parent without push/PR or external messaging.

Runner adapted from sink-probe runner52639f1a; code-only changes select the input-window CLI and its one-cell budget, source, parameters and method provenance. AST check and uv sync perform no benchmark construction/evaluation.
