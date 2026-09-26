# round15o measurement

- Runner T0/T1 (UTC): 2026-09-24T19:49:51.636575Z / 2026-09-24T19:57:06.369385Z; batch wall: 434.7334140999992 s.
- Spec commit: 8bac0f3c4e8159434e64807a61d8e89a74a65dbe; 30 cases, 5 cores, gap_packet; 30 solver + 30 official E0 calls; all cases ok.
- Validation: export valid (30/30); analyze 30 solver / 30 E0; audit passed, 60 gzip and 497097 trace operations verified; partial arithmetic mean speedup 3.995987.
- Host: Windows-11-10.0.26200-SP0, Python 3.12.14; free RAM at launch 1697200 KiB. Shared P1/P3/OS load not independently attributable; partial batch mean, not full-500.
