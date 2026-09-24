# Native proxy kernel exploration

This directory isolates a small, dependency-free ranking kernel that can be
implemented identically in Python, C++17, and Rust. It is an engineering
experiment for language and serialization comparisons. It is **not** the
official evaluator interface, it does not consume official graph/plan JSON,
and it is not evidence that E2 has low error against E0.

## Protocol and score

Input is ASCII tab-separated text. The first line is exactly
`NATIVE_PROXY_V1`; every following non-empty line has eight fields:

```text
candidate_id  pipe_bound_q6  dependency_bound_q6  copy_bytes  bandwidth_bytes_per_cycle  cross_task_count  cross_core_count  imbalance_ppm
```

The separators above are tabs. Candidate IDs match `[A-Za-z0-9_.-]+`, all
numeric fields are unsigned 64-bit decimal integers, bandwidth is positive,
IDs are unique, and `cross_core_count <= cross_task_count`.

The exploratory score uses checked unsigned integer arithmetic:

```text
compute_q6               = max(pipe_bound_q6, dependency_bound_q6)
transfer_q6              = ceil(copy_bytes * 1_000_000 / bandwidth_bytes_per_cycle)
communication_penalty_q6 = 25_000 * cross_task_count
                           + 225_000 * cross_core_count
imbalance_penalty_q6     = max(imbalance_ppm - 1_000_000, 0)
score_q6                 = sum(the four components)
```

Rows are ranked by `(score_q6, candidate_id)` in ascending order. Output is
canonical ASCII TSV with LF line endings and a final LF. Fixed-point integers,
checked overflow, and binary stdout on Windows make byte comparison meaningful.

## Reproduce

Run the language-independent tests:

```powershell
uv run python -m unittest discover -s tests/eval_proxy_native -v
```

Run compilation, byte comparison, and end-to-end process timing from a shell
where the desired compilers are on `PATH`:

```powershell
python src/eval_proxy/native/run_experiment.py --candidates 512 --iterations 11
```

For Visual Studio on Windows, initialize its environment first:

```powershell
cmd.exe /d /s /c '"%ProgramFiles%\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat" -arch=amd64 >nul && ".venv\Scripts\python.exe" src\eval_proxy\native\run_experiment.py --candidates 512 --iterations 11 --seed 20260923'
```

The driver builds into an OS temporary directory, never into the repository.
It compiles whichever of C++ and Rust are available, records a missing
toolchain as `unavailable`, and never treats an unavailable implementation as
a successful comparison. Use `--require-all` when both native toolchains are a
hard precondition.
