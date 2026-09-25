# 072/K5 Pipe interleave static probe

This archive preserves the completed, single-shot static probe. It is **not** an official E0 score. The frozen source commit is `8577916bc48cf2e8240aaecadce286c02b34eb20`; per-file source hashes, official graph/config hashes, and seed hashes are in `manifest-redacted.json`. `archive-index.json` records SHA-256 of every archived data file and the original source files. The original manifest and receipt remain under the local `output/` path; their archived copies replace personal absolute paths, with both original and redacted hashes retained. Preflight process details are not published.

The source seed is `seed-plan.json.gz` (c665 current 072/K5), and the constructed output is `retimed-plan.json.gz`. The probe began one constructor, called no E0/E1/E2 evaluator, and finished with exit code 0. Process wall time was 7.4303 s; total wall time was 7.4654 s. Observed peak process-tree RSS was 349,585,408 bytes (observer-inclusive 380,993,536 bytes).

Static checks found the owner/Pipe projection unchanged, global dependencies acyclic, mandatory transfer 113,241,428 bytes and FIFO lower bound 4,605,012 cycles. Before→after L1 modeled capacity peaks by core (bytes): 3,425,792→3,555,328; 3,393,072→3,696,176; 3,501,056→3,705,856; 3,453,056→3,697,664; 3,351,680→3,702,784. All five are worse in this model, so this retiming is a negative static result. No official evaluation was run, and this result does not show whether official E0 Makespan worsened.

Run this Python snippet from the repository root:

```python
import gzip, hashlib, json, pathlib
p = pathlib.Path('results/a/q2-nikolastarx/pipe-interleave-072-static-20260925')
i = json.loads((p/'archive-index.json').read_text())
for name, record in i['files'].items():
    b = (p/name).read_bytes()
    assert hashlib.sha256(b).hexdigest() == record['sha256'] and len(b) == record['bytes']
for name, raw_hash in i['compressed_raw_sha256'].items():
    assert hashlib.sha256(gzip.decompress((p/name).read_bytes())).hexdigest() == raw_hash
assert all(a['L1'] > b['L1'] for b,a in zip(json.loads((p/'static-result.json').read_text())['capacity_peaks_before'], json.loads((p/'static-result.json').read_text())['capacity_peaks_after']))
print('archive verified')
```
