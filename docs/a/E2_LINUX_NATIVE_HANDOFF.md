# E2 P2/P3 Linux native build handoff

This is a source-identical build route for the E2 research checkpoint
`603b0741e21c449d3db652ebd67c94f2dc014cc9`. It does not change the
existing macOS ARM64 binary or the P2 solver. The Linux `.so` gets its **own**
SHA-256 and manifest. The E2 library is C++17; Python uses `ctypes` to load it.

## Package and build

Use the fixed P2 manifest at
`results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json` from commit
`ee4fe0282ca2ff5d73bb23d54b1c213909e1401c`. Its exact byte SHA-256 is
`9ee379269c0c4f25b64f9d0aeaf1e397e85e48c2103b08637db356d3c9595387`.
It lists all 50 source files and their hashes. The manifest, this script and
the output receipt belong **outside** the E2 source capsule; the online P2
guard expects only listed source files plus one platform binary inside it.

On the source machine, export those files from the E2 commit (or use an
identical, hash-checked capsule):

```sh
git show ee4fe0282ca2ff5d73bb23d54b1c213909e1401c:results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json > fixed-p2-manifest.json
python3 - <<'PY'
import json, subprocess
names = list(json.load(open('fixed-p2-manifest.json'))['e2_sources'])
subprocess.run(['git', 'archive', '--format=tar', '-o', 'e2-603b-sources.tar',
                '603b0741e21c449d3db652ebd67c94f2dc014cc9', '--', *names], check=True)
PY
```

On Linux x86_64, unpack into a fresh `e2-src` directory. Use a Python with
the dependencies required by E2, including NumPy. `build` refuses an existing
binary or receipt, which prevents accidental reuse of the Mac library.

```sh
mkdir e2-src
tar -xf e2-603b-sources.tar -C e2-src
python3 scripts/e2_linux_native.py build \
  --root e2-src --source-manifest fixed-p2-manifest.json \
  --out e2-linux-build.json --compiler "$(command -v g++)"
python3 scripts/e2_linux_native.py verify \
  --root e2-src --source-manifest fixed-p2-manifest.json \
  --out e2-linux-build.json
```

Copy `scripts/e2_linux_native.py` separately to the Linux machine if it is not
part of the capsule. The commands make **zero** E0/E2 scoring calls. They
verify all source hashes, ELF64 x86_64 format, exported `replay_bc_abi()==1`,
Python `ctypes` layout, and the built binary hash. The JSON receipt records
the compiler executable hash/version/target, exact build command and flags,
Python/NumPy ABI, libc/platform, dynamic dependencies and UTC build time.
Keep the original receipt bytes and record their SHA-256 in the run ledger.

## P2 integration boundary

The current P2 `check_e2_source` in `adaptive_guarded.py` intentionally accepts
only macOS ARM64 and its pinned binary SHA. The P2 owner should add a separate
Linux branch that requires the verified Linux receipt, exact binary SHA,
source SHA list and platform/ABI match. Do not replace the macOS constant with
the Linux hash or copy the Mac `.so` into Colab. Verify before the first online
call; charge verification time to the solver's end-to-end wall clock.

The existing child-worker condition `route == "native"` must remain mandatory.
`SceneBEvaluator` may automatically use E0 on unsupported/error paths, so a
successful API response alone does not prove native execution. Count attempts,
native returns, possible/actual E0 fallback and final E0 separately. A Linux
build and ABI check prove loading only; a later **authorized**, fixed-plan
comparison with independently saved E0 results is needed before making any
Linux numerical-equivalence or performance claim. Do not infer P3 coverage
from a P2 comparison.
