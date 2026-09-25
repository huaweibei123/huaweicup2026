# Unified hypergap cold CLI check

One cold invocation of fixed solver `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` on 003/k5 completed in 10.175904708 seconds, including input read, baseline/gap/hypergap construction, three native E2 requests, and selected plan output. The same pinned 603b native backend returned baseline M515736/addedDDR393216B, gap M205295/9845480B, and hypergap M163449/5637616B. No fallback or unknown request occurred.

The selected plan was read back and compared structurally with the independently E0-evaluated three-cell pilot at commit `f8d03227d9662a8bea8f7e30cb1bc5a09fb6f409`; it is identical. Its E0 M163449 is reused from that exact-input, exact-config, exact-plan evidence. This check made 1 solver + 3 native E2 calls and **zero new E0/E1 calls**. It is an entrypoint check, not a whole-dataset result. The process ran on a shared Mac while the older frozen gap batch retained its single worker.

`protocol.json` records the command, frozen source hashes and 60-second/4-GiB/zero-retry limits; `process/process.json` records end-to-end wall time and process cleanup; `online/solver.json` records every native plan hash and score; `check.json` records readback. Later whole-dataset experiments use a separate fixed runner and output directory.
