# 016 k5 controlled-split static construction

Source `d1cb26fe04cd7f0a49c053fde8b0e97d3c9b5780`, original graph/config SHA-256 and source file hashes in [report.json](report.json). One original-case construction completed in 0.398925 s, with a 15-second alarm and poisoned evaluator/subprocess calls during construction. This is static work, **zero official E0/E1/E2**. The script is committed with these results; the algorithm source was committed before construction.

Full eligible coverage and original compute plus V FIFO acyclicity passed. Plan SHA-256 `a325000217e63bc1c37f16301712b27e210423db70a19be677b4f0ddcb1a9269`; only the hash is stored to avoid a duplicate large plan. The fixed-candidate minimum-lag lower bound is 1,931,673 cycles. It is not an achieved time or a global bound. Estimated additional large-vector COPY is 39,976,960 bytes, before scalar COPY/spill. Original compute-touch peaks fit configured pools but exclude generated COPY/Step3 edges and do not certify zero spill.

The candidate is worth one falsification run because its lower bound does not rule out improving the existing 2,240,622-cycle official result. A low bound alone is not a predicted improvement. P1 released its test window before this static run; s59 was notified of the release afterward. No b7 unified benchmark cell has been dispatched here.
