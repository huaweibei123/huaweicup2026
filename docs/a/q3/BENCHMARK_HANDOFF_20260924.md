# Q3 稳定候选：跨平台语义复核

仅向成绩台调度 session s7c98 交付，由其统一给 LYX/farmer 排队；不直接给两位同时派单，
不扩大在途批次。P3 算法写范围仍归 session 3172。此次 runner 修订只做零评分软件验证，
没有重跑原 20 格或下面 5 格，Windows 原生实机尚未验证。

## 算法与 runner 分开固定

- 算法：`6389818b1028ada74c685483dd1cd75fb8e16285`，入口 `src.q3.guarded_solve`，原件字节不变。
- **runner 使用包含本兼容修订的另一个固定提交**。维护者提交后交付其完整 SHA；成员在该
  runner 提交新建干净 worktree。模板的 `REPLACE_WITH_FIXED_PORTABLE_RUNNER_SHA` 故意不可执行，不能填旧 638 或猜测发布版本。
- 控制原件：`11bd277697839b14f513bdb3e38cf7a4d43d913a`，
  `results/a/q3-nikolastarx/guarded-20260924/`。模板逐格声明 plan/result/receipt 路径与 SHA256；
  runner 从这个固定 Git 提交读取，不能拿工作区中后来修改的成绩当 expected。
- 官方源码集合 SHA256：`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。
- config SHA256：`dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。

638 guarded 的本地依赖闭包是 `src/q3/` 下的 `__init__.py`、`guarded_solve.py`、
`safe_solve.py`、`solve.py`、`construct.py`、`reduction_tree.py`、`release_tree.py`、
`capacity_tree.py`、`pipe_bound.py`。这是审过该固定入口（包括函数内 import）的清单，
不是适用于未来任意动态 import 的自动证明。每个文件同时比对模板 SHA、638 Git 原件和实际
运行文件，9 项缺一不可；`src/__init__.py` 必须仍不存在（namespace package）。
`uv.lock`、`pyproject.toml`、冻结 source-manifest 也须与 638 相同；官方全部源码、config 和
本批各图另按 source-manifest 校验。清单外新增 stage 模块、非依赖 `tree_solve.py` 的变动，
不改变这个算法身份；实际 checkout 的全部 Q3 文件仍记录哈希，并在 job 前后检查漂移。

运行 worktree 的 HEAD 必须等于新 runner SHA，tracked 文件干净，不能有未跟踪的 src Python
文件。工作区里已有 `.pyc` 不作为算法来源：子进程使用新的空 pycache prefix，且 `-B` 禁止
写回；不删其他会话缓存。哈希相同不等于独立复现成功，结果比对仍须完成。

## 五格范围

| case/k | 预期最终官方 cycles（待对方核） | 预期在线 E0 | 验证理由 |
|---|---:|---:|---|
|002/3|93527|1|下界 94428 剪枝，未评分 plan/hash 保留|
|062/5|588101|2|anchor 673177 后接受 release|
|063/5|232381|2|anchor 336337 后接受 release|
|080/4|83124|1|未切分多树保旧交错，spill 229376 仍合法|
|008/5|52291|1|resource-word 守卫外保持既有算法|

目的：另一台机器上独立确认官方值/类型、计划身份、选择、剪枝和回退行为；不把不同硬件
墙钟相除解释成算法效率提升，不预称对方复现成功。

## 两次提交的冻结顺序

1. 维护者先提交 runner、exporter、tests 和软件验证，得到 **RUNNER_SHA**。
2. 再只更新本 handoff 和请求模板的 `execution.runner_commit=RUNNER_SHA`，提交得到
   **HANDOFF_SHA**，同时交付两个完整 SHA。无需也不能运行新 E0 来产生这两个提交。
3. 成员必须 checkout **RUNNER_SHA**；使用 `git show HANDOFF_SHA:...` 读取后一次提交的
   请求模板并写成未跟踪运行副本。**不能 checkout HANDOFF_SHA**，否则实际 HEAD 与
   runner_commit 不同，预检应该拒绝；也不能自行改 runner_commit 来掩盖差异。

## 准备与运行

先等调度者明确分配及 runner 完整提交。创建本人独立验证 worktree，不在研发 owner 的目录
执行或修改源码；Windows checkout 应保留 Git 中 LF 原字节，例如在创建 worktree 的命令上
使用 `git -c core.autocrlf=false worktree add --detach <本人新目录> <RUNNER_SHA>`，不改全局设置。
若现有 checkout 已经转成 CRLF，重新建本人目录，不能在团队工作区批量改行尾。

`uv sync --locked` 后，用项目 Python 执行下面准备代码，替换本人身份和唯一 run/runtime 名称。
准备代码可在交互解释器或编辑器中执行，不放进 `src/`。只写未跟踪的运行副本，不能修改
已跟踪模板来通过检查；用 Python UTF-8 写文件，不用旧 PowerShell 可能产生 UTF-16 的重定向。

```python
import json, subprocess
from pathlib import Path
handoff_sha = "REPLACE_WITH_FULL_HANDOFF_SHA"
request_path = "results/a/q3-nikolastarx/guarded-20260924/benchmark-request-5cells.json"
m = json.loads(subprocess.check_output(["git", "show", f"{handoff_sha}:{request_path}"]))
actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert actual_head == m["execution"]["runner_commit"], "checkout RUNNER_SHA, not HANDOFF_SHA"
m["producer_session"] = "REPLACE_WITH_MEMBER_LOGIN_AND_SESSION"
m["run_id"] = "REPLACE_WITH_UNIQUE_RUN_ID"
m["runtime_id"] = "REPLACE_WITH_ACTUAL_HOST_ID"
p = Path("results/a/q3-verification/member-5cells.manifest.json")
p.parent.mkdir(parents=True, exist_ok=True)
with p.open("x", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
```

运行前可以只做 manifest/源码/控制原件预检，不启动求解器：

```python
from pathlib import Path
from src.q3.feedback_benchmark import ROOT, read, validate_manifest, verify_manifest_source, load_expected
m = read(Path("results/a/q3-verification/member-5cells.manifest.json"))
validate_manifest(m)
verify_manifest_source(m, [j["case_id"] for j in m["jobs"]], ROOT)
load_expected(m, ROOT)
```

确认调度许可后才执行；`NEW_RUN`、`NEW_FEED` 替换成自己唯一名称且输出目录必须不存在：

```sh
uv run python -m src.q3.feedback_benchmark results/a/q3-verification/member-5cells.manifest.json results/a/q3-verification/NEW_RUN
uv run python -m src.q3.board_export results/a/q3-verification/NEW_RUN/batch.json results/a/q3-verification/NEW_FEED.json
```

runner 的新 verification profile 与 exporter 均允许该目录；解析真实路径后拒绝 `..`/软链接
逃逸，不开放整个仓库写区。旧研究 manifest 不加 `execution` 时仍限定原 `q3-nikolastarx` 写区、
原预算和原同提交身份；本修订不替它默认追加 expected 或内存探针。

## 预算、超限和清理

唯一 5 job，最多 10 次新 E0、1 CPU worker、90 秒/job、600 秒批次，预期 7 次 E0。
无 GPU/Colab、随机搜索、重试、新单核分母或 P2 评分。失败时 actual E0 不明就留 null 并
保留完整预约；可读且已核的成功 receipt 证明调用数后，即使 expected 不一致仍记录实际调用，
但失败格不退还预算，也不继续派下一格。

模板明确 `execution.memory_limit_bytes=8589934592`（8 GiB），`memory_poll_seconds=0.1`。
内存口径为 POSIX 同进程组 RSS 合计 / Windows Job 内各进程 WorkingSetSize 合计，含子进程；
共享页面可能重复计数。它是**采样阈值触发停止**，不是 OS 硬限制或精确峰值：采样与查询开销
之间可能短暂超限。发生超限或探针失败，记录原因、杀子树、保存日志、停止全批，不静默无监测运行。
监测本身计入全进程 wall；采样最大值在每格 solver_process.memory 中保留，不能冒充硬峰值 RSS。

POSIX 使用独立 process group，超时/中断/收尾清理该组。Windows 使用原生 kill-on-close
Job Object 和等待许可的 launcher：先成功把 launcher 归入 Job，才允许它启动 solver；所有
后代继承 Job，超时关闭或父进程退出触发清理，不调用 POSIX killpg。若机器的 nested-job
策略禁止归组，在 gate 打开前失败；不退化为仅杀父进程。清理 reap 最多另等 10 秒，实际
清理/日志开销仍计入 wall，不把 90 秒写成含所有异常清理的绝对硬实时保证。

Windows 实现依据微软 [Job Object 查询接口](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)、
[扩展限制结构](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)、
[进程内存计数](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters)。
文档和 API 替身测试不替代 Windows 机器上的原生运行验证。

## 逐格比对与输出

每格自己的官方证据先按原 runner 合法身份/选优/哈希检查，再在**下一格 dispatch 前**对照
固定控制原件：最终 plan 原字节 SHA、完整官方 JSON 全字段值及类型（int/float 不混同），
以及 receipt 的调用数、selected_strategy、候选 name/strategy/status/makespan、剪枝下界和
未评分计划哈希。JSON 对象键顺序和 gzip 容器元数据不要求一致；不排除任何官方诊断字段。
receipt 的 wall/timer 不参与固定值比较，这是明确排除的机器相关字段。

出现差异保存 `expected-comparison.json`（每类别最多 20 个具体差异路径），保留原结果和日志，
标记 failed 并停止全批；不能归一化数值、以相同 Makespan 忽略其它字段或自动重试。
仅哈希/expected 原件缺失在派发前就失败，不启动任何 E0。源码在格间变化也停并记录原因。

最终每格保全两字段 plan、所有已评分候选完整 E0 gzip、剪枝计划、receipt、ledger、日志、
argv、机器/解释器/依赖与实际源码身份、端到端 wall。feed 的 solver source 仍是 638，runner
source 单独使用新提交。Windows launcher 的额外启动成本包含在 wall，不能与旧本机单进程
墙钟直接作因果比较。已有 8 个官方单核分母可按旧来源/SHA 复用到本人目录，绝不重跑。

软件检查只用合成原件和很小的 Python 子进程：成功、超时、后代清理、内存超限、监测失败、
中断保日志、Windows gate/Job 路由、源码/路径/UTF-8、expected 值/类型错即停止；构造器和
E0/E1/E2 均不调用。实际 Windows Job/API、另一硬件数值与这 5 格独立复跑仍是交接后的未验项。
完整正负结果向成绩台 owner 和算法 owner 回报；成功不自动扩成 15/500 格。
