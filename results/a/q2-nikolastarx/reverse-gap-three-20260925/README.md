# Reverse-time chain/join three-cell mechanism probe

One frozen raw-input constructor at `6836516874ce9e65d85ab2deed206e22d77b1562` was evaluated by unmodified official P2 E0 on 005/069/071 K5. This is a mechanism probe, **not a new full500 benchmark**. All three results are legal, zero spill; two improve Makespan while 005 regresses sharply. All three increase added DDR. Therefore the candidate cannot replace the current solver globally.

| Case K5 | Old official M | Reverse M | M reduction | Old added DDR B | New added DDR B | Cold constructor s | External E0 s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 005 | 33515 | 43881 | -30.9294% | 1410582 | 2106200 | 4.2860 | 2.0789 |
| 069 | 11962 | 10577 | 11.5783% | 321938 | 452436 | 0.8145 | 0.5064 |
| 071 | 9465 | 8456 | 10.6603% | 273776 | 329202 | 0.6042 | 0.4001 |

The virtual reversed chain DAG changes placement priorities, then restores each core's forward order. It never reverses raw tensor producers/consumers. The static calendar ignores dynamic DDR, capacity and spill; its model finish is not an official prediction or lower bound. Old scores refer to the same input/config coordinates of frozen c665 full500, with identities in `freeze.json`. Selecting winners from this table offline is not a submitted algorithm. A future general online wrapper must preserve the complete incumbent and count all scoring/selection wall time.

## Execution and verification

One admitted Colab CPU Standard VM, one worker, 3 constructor / 3 external E0 calls, E1/E2/retries 0. Each child limit30s; batch120s; observer-inclusive RSS512MiB; outer exec145s and VM lease300s. Remote batch ran 2026-09-25T11:06:36.998559Z–11:06:45.778036Z. Outer observer-inclusive peak RSS200646656B; all six child receipts exit0 with no survivors. Command/process originals are retained, but exact cloud Python/kernel/hardware versions were not separately captured before VM release. This limits environment reproduction; these remote wall times do not establish local-Mac performance.

`results.zip` contains 41 original members (ledger, plans, E0 results/traces/logs and process receipts), SHA256 `71d8805830ce18ec60e4aef89ffb621e184005f6e1d2e0ccb373c5196cbe6194`, 718951B. Root independently checked CRC, identities, plan/result/solver hashes, coordinates, calls, timing limits and survivors; see `verified-results.json`. Input capsule SHA256 `026750d8bcd8ad927a50dc6f628ff20836e28936e3b04843acf8b373d55f7581`, 437692B/83 members. It transports 75 frozen source files, fixed config,3 raw inputs, freeze and authentic commit object, plus launcher/manifest. Its Git object store reconstructs the authentic commit SHA for the frozen HEAD check; it is not a full checkout/history. Seventy-five source hashes and original input hashes are independently verified.

The first packaging draft had a detected output-directory collision and was corrected before any real call; the final frozen ZIP is the only executed package. The published controls exactly match that final dispatch. `build.py` was a local packaging helper and is omitted; runtime originals are retained.

**T0 bookkeeping exception:** the executor captured host free memory/swap/pressure, empty sessions and no-local-scorer checks before launch, but writing the T0 JSON used an incorrect relative path and failed. The shell then launched the controller once. `execution-audit.json` was reconstructed afterward from that tool output and is explicitly not a contemporaneous T0 file. No score rerun was used to hide it. Named VM stop returned0, fresh sessions were empty and the watchdog was reaped; release evidence is separate from algorithm acceptance.

Publication does not promote these three cells into formal benchmark data. Formal frozen c665 K5 mean remains4.549756996698352. Next bounded step is a general forward/reverse online choice retaining incumbent on errors, followed by separately admitted validation on untested structures.
