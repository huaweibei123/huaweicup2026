# P2 existing-evidence comparison

0 new E0/E1/E2. Frozen comparison time: 2026-09-24T14:45:49.529895+00:00.
Development-subset results are not a full100 average. Wall values are observations, not causal speedups.

| Case/core | Status | Evidence | Makespan | vs Fang | vs history | Extra delta Fang/history | Spill delta Fang/history | Solver wall s | U-L |
|---|---|---|---:|---|---|---:|---:|---:|---:|
| 002/2 | ok | artifacts_verified | 131796 | win | win | 4104192/4104192 | 1087488/1087488 | 0.21988787499140017 | 11616 |
| 008/2 | ok | artifacts_verified | 125682 | win | win | 0/0 | 0/0 | 0.19795129101839848 | 618 |
| 014/2 | ok | artifacts_verified | 13097894 | loss | loss | 280461376/280461376 | 136591968/136591968 | 1.5025997920020018 | 4484900 |
| 016/2 | ok | artifacts_verified | 9260226 | loss | loss | 419375820/419375820 | 379715584/379715584 | 0.5035342500195839 | 5402732 |
| 025/2 | ok | artifacts_verified | 4251120 | loss | loss | 100832256/100832256 | 100832256/100832256 | 0.7364165830076672 | 1899672 |
| 035/2 | ok | artifacts_verified | 128427 | win | win | 3319830/3319830 | 0/0 | 0.2819455420249142 | 56472 |
| 062/2 | ok | artifacts_verified | 2262944 | win | win | 76139520/76139520 | 42378240/42378240 | 0.7395895000081509 | 953600 |
| 071/2 | ok | artifacts_verified | 16870 | win | win | 301856/301856 | 0/0 | 0.19321704198955558 | 10436 |
| 002/4 | ok | artifacts_verified | 78812 | win | loss | 2491392/2371584 | 0/0 | 0.22390362501027994 | 18632 |
| 008/4 | ok | artifacts_verified | 63768 | win | tie | 0/0 | 0/0 | 0.19686045800335705 | 1236 |
| 014/4 | ok | artifacts_verified | 8292269 | win | win | 294162504/294162504 | 81027168/81027168 | 1.7552508749940898 | 3985712 |
| 016/4 | ok | artifacts_verified | 2250687 | win | win | -836788/-657164 | 0/0 | 0.5877250830235425 | 321927 |
| 025/4 | ok | artifacts_verified | 2585433 | loss | loss | 95232000/95232000 | 91075584/91075584 | 0.9433253750030417 | 1409433 |
| 035/4 | ok | artifacts_verified | 105911 | win | win | 3435782/3435782 | 0/0 | 0.2893580420059152 | 69933 |
| 062/4 | ok | artifacts_verified | 1607053 | loss | loss | 65048064/65048064 | 31706112/31706112 | 0.8931887079961598 | 952309 |
| 071/4 | ok | artifacts_verified | 13146 | win | win | 275204/275204 | 0/0 | 0.1983055000018794 | 9776 |
| 002/5 | ok | artifacts_verified | 72043 | win | win | 1976832/1976832 | 0/0 | 0.21800812499714084 | 23863 |
| 008/5 | ok | artifacts_verified | 52291 | win | win | -111360/-111360 | 0/0 | 0.19638345899875276 | 1339 |
| 014/5 | ok | artifacts_verified | 7364271 | loss | loss | 314476052/314476052 | 89939040/89939040 | 2.051492833008524 | 3919001 |
| 016/5 | ok | artifacts_verified | 2240622 | win | win | -1291244/-1291244 | 0/0 | 0.629152959008934 | 697606 |
| 025/5 | ok | artifacts_verified | 2279371 | loss | loss | 92461056/92461056 | 88224768/88224768 | 0.905528500006767 | 1338571 |
| 035/5 | ok | artifacts_verified | 99765 | win | win | 3167042/3167042 | 0/0 | 0.2898982500191778 | 70983 |
| 062/5 | ok | artifacts_verified | 1391629 | loss | loss | 58639872/58639872 | 29870592/29870592 | 0.9463200419850182 | 867793 |
| 071/5 | ok | artifacts_verified | 11332 | win | win | 239430/239430 | 0/0 | 0.22965687501709908 | 8414 |

Full per-attempt evidence errors, ratios, identities, calls and scope are retained in the JSON.
