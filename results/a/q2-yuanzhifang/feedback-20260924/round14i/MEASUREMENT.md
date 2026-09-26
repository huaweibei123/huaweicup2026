# round14i measurement

- Runner T0/T1 (UTC): 2026-09-24T19:02:20.668537Z / 2026-09-24T19:08:25.940322Z; batch wall: 365.27190589999736 s.
- Spec: round14i-spec.json; 26 cases, 3 cores, gap_packet; 26 solver + 26 official E0 calls, 0 retries; all cases ok.
- Validation: export valid (26/26); analyze 26 solver / 26 E0; audit passed, 52 gzip and 388027 trace operations verified; partial arithmetic mean speedup 3.081791.
- Host: Windows-11-10.0.26200-SP0, Python 3.12.14; free RAM before launch 3743788 KiB. Shared host; concurrent P1/P3/OS load not independently attributable; batch mean is partial, not full-500.
