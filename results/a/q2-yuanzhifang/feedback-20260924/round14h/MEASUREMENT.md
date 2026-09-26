# round14h measurement

- Runner T0/T1 (UTC): 2026-09-24T18:54:39.960231Z / 2026-09-24T18:59:49.429935Z; batch wall: 309.4694019999988 s.
- Spec: round14h-spec.json; 33 cases, 3 cores, gap_packet; 33 solver + 33 official E0 calls, 0 retries; all cases ok.
- Validation: export valid (33/33); analyze 33 solver / 33 E0; audit passed, 66 gzip and 356702 trace operations verified; partial arithmetic mean speedup 2.861684.
- Host: Windows-11-10.0.26200-SP0, Python 3.12.14; free RAM before launch 2419980 KiB. Shared host; concurrent P1/P3/OS load not independently attributable; batch mean is partial, not full-500.
