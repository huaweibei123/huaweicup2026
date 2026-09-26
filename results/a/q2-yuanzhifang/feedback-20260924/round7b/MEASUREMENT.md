# P2 7B 二核测量

`round7b-parallel3-spec.json` 唯一运行，33图均成功：33 solver、33独立未修改官方E0、E1/E2为0，单worker、无重试。T0 `2026-09-24T17:26:02.264241Z`，T1 `2026-09-24T17:30:38.067946Z`；批墙钟 275.803380 秒，批前固定字节预检另计 9.633347 秒。solver墙钟合计49.140707秒，E0合计201.597241秒。

本批官方单核基线逐图 B/M 算术均值 1.878830972，只代表33图。`export_board` 内置preflight为33 records/33 eligible；`analyze` 成功。`audit_saved.py` 独立只读核查66份gzip原始/存储哈希、固定源码、feed引用、252394个trace操作区间、基线身份及单worker阶段顺序，退出码0。逐图cycles、搬运量及墙钟在 `measurement-audit.json` / `summary.csv`。测量发生在共享资源和未控制OS缓存下。
