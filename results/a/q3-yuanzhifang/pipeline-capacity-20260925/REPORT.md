# Capacity-constrained pipeline: case044, four cores

Frozen solver `2df4a5fa70d7a59492a7477e9ecd706501e64ad6`, runner `a7802a069a73accd0f24d0eb8b81a636c74b4648`. The earlier capacity prototype rejected legal raw DDR COPY endpoints; the corrected guard was checked by seven synthetic tests before this pilot. No earlier official score of that prototype is claimed.

Luna medium ran one cold construction and two external E0 calls, with zero retry/E1/E2. T0 `2026-09-24T19:59:06.781000Z`, T1 `19:59:37.575472Z`, total30.795380s. Windows Ryzen5600H host shared with P2; one below-normal child at a time. The three RAM checks passed the fixed1GiB gate, minimum1,984,036,864B. Cold solver wall2.724028s, external P2/P3 walls2.584837/9.150610s. These single shared-host observations do not establish an efficiency gain over the historical0.695627s control.

|metric|fixed compute-balanced pipeline|capacity pipeline|
|---|---:|---:|
|P2 Makespan / cycles|40927|37581|
|P3 Makespan / cycles|40927|37581|
|extra DDR / bytes|135168|121088|
|spill / bytes|0|0|
|P3 byte cache hit rate|0|0|

The old control is fixed `e6b5500dcbf3818034804168ee79d0f65c16706b`; it was verified and not re-run. The new plan differs in raw bytes and parsed structure, SHA-256 `715be4ece4ebc6d5db625efd2f7adb6a439e37b0e1f1e7f0a4a16a190b039a7c`. It contains the legal two fields,1364 singleton compute subgraphs,11 jobs and124 positions. Cuts are `[0,41,65,95,124]`, stage compute cycles `[2822,1388,1728,1734]`, nominal first-job setups `[1232,8605,5493,200]`. No online E0, candidate sweep or case-name rule was used.

Official Makespan improves3346 cycles (8.175532%) and extraDDR falls14080B (10.416667%). P3 reports0 hit bytes/1,013,472 miss bytes; improvement is not attributable to higher cache hit rate. This is a one-case four-core result, not full-family generalization, a unified100x5 score or unrestricted optimality proof.

The simplified constrained flowshop predicts40542, while actual E0 is37581; that abstraction is neither an E0 lower nor upper bound in general. Modeled L1 requirements `[79584,516864,330752,17792]` differ from official peaks `[79584,516992,330752,18816]`. All official UB peaks are0. The static surrogate is not an exact lifetime analysis or zero-spill certificate even though this measured plan has no spill.

All plan/result/trace/log, stdout/stderr, commands, config/graph/source hashes, paired scenarios and actual official single-core denominator are sealed in this directory. The exporter produced two candidate records. Fixed-commit format/byte precheck follows as a separate receipt; central admission and independent scientific review remain separate.
