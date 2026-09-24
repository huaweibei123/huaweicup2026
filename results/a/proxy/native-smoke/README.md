# Native proxy smoke result

Run date: 2026-09-23

This is a synthetic engineering check of the isolated fixed-point ranking
kernel in `src/eval_proxy/native/`. It is not an official evaluator run, does
not use official graph/plan I/O, and does not establish E2 error against E0.

The run generated 512 candidates with seed `20260923`, compiled the C++17
implementation with Microsoft C/C++ 19.35.32215, and compared complete stdout
bytes with the Python reference. Both produced 31,387 bytes with SHA-256
`30b2a06e4fde37cb43f5feb59e7e0735049e2c610e35eb09fd5238a5e25f3186`.

| implementation | status | byte equal | median process ms | p95 process ms |
| --- | --- | ---: | ---: | ---: |
| Python 3.12.13 | pass | yes | 256.8738 | 358.1325 |
| MSVC C++17 | pass | yes | 39.4891 | 55.1419 |
| Rust | unavailable | not run | not measured | not measured |

Each timing has one warmup and 11 measured launches. It includes process
startup, input parsing, ranking, and serialization, so it is a basic local
end-to-end observation rather than an in-process kernel benchmark.

Rust was not run because neither `rustc` nor `cargo` was on `PATH`; this is a
real untested item, not a passing comparison. The Rust source and exact build
command are retained for a host with that toolchain. See `report.json` for
input/output hashes, compiler command, environment, and machine-readable
status. Compilation used an OS temporary directory; no executable or object
file is retained here.

Reproduction command, including the Visual Studio developer environment used
for this run:

```powershell
cmd.exe /d /s /c '"%ProgramFiles%\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat" -arch=amd64 >nul && ".venv\Scripts\python.exe" src\eval_proxy\native\run_experiment.py --candidates 512 --iterations 11 --seed 20260923 --report results/a/proxy/native-smoke/report.json'
```
