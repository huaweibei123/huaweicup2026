# round15m measurement

- Runner T0/T1 (UTC): 2026-09-24T19:36:05.568727Z / 2026-09-24T19:40:32.290831Z; batch wall: 266.7220648000002 s.
- Spec commit: 8bac0f3c4e8159434e64807a61d8e89a74a65dbe; 21 cases, 5 cores, gap_packet; 21 solver + 21 official E0 calls; all cases ok.
- Validation: export valid (21/21); analyze 21 solver / 21 E0; audit passed, 42 gzip and 266153 trace operations verified; partial arithmetic mean speedup 3.672205.
- Host: Windows-11-10.0.26200-SP0, Python 3.12.14; free RAM at launch 1935680 KiB. Shared P1/P3/OS load not independently attributable; partial batch mean, not full-500.
