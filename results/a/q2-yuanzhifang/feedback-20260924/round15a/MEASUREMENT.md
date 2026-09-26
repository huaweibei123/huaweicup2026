# round15a measurement

- Runner T0/T1 (UTC): 2026-09-24T19:58:44.260491Z / 2026-09-24T20:03:36.407234Z; batch wall: 292.14732509999885 s.
- Spec commit: 8bac0f3c4e8159434e64807a61d8e89a74a65dbe; 33 cases, 5 cores, gap_packet; 33 solver + 33 official E0 calls; all cases ok.
- Validation: export valid (33/33); analyze 33 solver / 33 E0; audit passed, 66 gzip and 238284 trace operations verified; partial arithmetic mean speedup 1.153446.
- Host: Windows-11-10.0.26200-SP0, Python 3.12.14; free RAM at launch 2345924 KiB. Shared P1/P3/OS load not independently attributable; partial batch mean, not full-500.
