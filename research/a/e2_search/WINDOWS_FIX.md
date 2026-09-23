# Windows worker 修复：独立定点回归交接

来源：Fang 固定 PR44 / 6aad0ef09521913de49fb91c5624fd8194e1728e，
[实际测试回执](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5803290603)。
原被测 f4ee475、原 P1 PR42 不改；本修复单独提交，可在独立测试 checkout 应用。

1. Windows 读取 `K32GetProcessMemoryInfo` 的 `PeakWorkingSetSize`；DWORD 为32位，SIZE_T随指针宽度。
   Linux/macOS 保留 resource 方式。不是进程硬内存限额。若设置回收阈值而遥测不可用，
   明确返回 `recycle_reason=rss_telemetry_unavailable` 并在下个请求前回收，不再静默跳过。
2. 请求期限改用 `perf_counter`，避免此 Windows/Python 环境 `monotonic` 的15.625ms粒度
   使极短期限在同tick读成0。保留启动与请求期限分离；不声称测试证明秒级超时原来失效。
3. LLVM-MinGW 动态库仍需同版本匹配的运行库。Fang 已证实自己的工具链需要 libc++.dll/libunwind.dll；
   请使用已验证发行包中的对应 DLL，放在 native DLL 可查找目录（例如相邻目录），记录来源/哈希并检查实际route。
   编译成功不等于DLL可载入；缺依赖时保持显式fallback，不自动安装或更改系统PATH。构建仅支持现有GCC/Clang风格参数，
   不把 cl.exe 当作可直接替换的编译器。本次不重打包/提交第三方运行库。

定点命令（先按所选问题显式构建）：

```sh
uv run python -m unittest research.a.e2_search.tests.test_resources -v
uv run python -m unittest research.a.e2_search.tests.test_search.SearchTest.test_pool_order_error_recycling_and_cleanup research.a.e2_search.tests.test_search.SearchTest.test_pool_timeout_crash_cancellation_and_stream_bound -v
```

仅用合成图，正常不需要任何正式图E0。报告Python/系统、两个clock的实现/分辨率、RSS值、回收前后PID、
8次极短timeout实际状态、秒级正常任务、native/fallback路由和DLL身份。本机macOS实测与ctypes ABI注入不代替Windows执行；
Windows定点复核由原测试协调明确安排，不自动重跑64正式候选或488总调用。

依据：[Microsoft API](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)、
[结构及字节单位](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters)、
[Python 3.12 perf_counter](https://docs.python.org/3.12/library/time.html#time.perf_counter)。
