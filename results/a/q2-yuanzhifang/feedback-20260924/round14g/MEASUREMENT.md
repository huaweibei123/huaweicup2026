# round14g measurement

- Runner T0/T1 (UTC): 2026-09-24T18:47:38.194116Z / 2026-09-24T18:52:00.833579Z; batch wall: 262.63912880000134 s.
- Spec: `round14g-spec.json`; 33 cases, 3 cores, `gap_packet`; 33 solver calls + 33 official E0 calls, 0 retries. All cases status `ok`.
- Validation: export valid (33/33); analyze reports 33 solver / 33 E0; audit passed, 66 gzip verified, 260819 trace operations verified; partial arithmetic mean per-case speedup is 3.016138 (single-core baseline makespan / three-core makespan); not a makespan or a full-500 mean.
- Host: Windows 11 / Python 3.12.14 runtime per spec; free RAM before launch 3270968 KiB (>=1.5 GiB). Shared host; other P1/P3 and OS workload were not independently attributable. This is one 33-case batch mean, not the full 500-cell result.



