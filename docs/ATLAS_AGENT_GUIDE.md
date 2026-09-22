# 比赛期 Atlas：先做题，按交接点维护

入口：[System Atlas](SYSTEM_ATLAS.md)。Task Board 管当前分工；`tasks/` 任务卡保存输入、验收和复现约定；Issue 处理需要他人行动的交接；PR 交付代码。不要把同一份进度流水账复制到三处。既有预演已经结束，正式协作不能沿用被撤销的预演权限。

## 最小维护约定

- 一个任务对应一个可交付成果，有一个明确主负责人和验收标准。`assignees` 是标签，不授予权限或唤醒 Agent。小步骤留在自己的工作记录里，不逐条建卡。
- 开始实质工作时更新一次 `doing`；出现影响他人的阻塞时写明 `blocked`；交付时一次原子请求写 `review` 和 `deliverables`，后者只放 PR、结果、复现命令的引用。验收者看实际结果后再置 `done`。这是团队约定，服务不强制人审门禁。
- 持续做实验期间不反复更新状态、重发“收到”或轮询全图。阻塞解除时清空 `blocked`。做不完就如实保留当前状态。
- 任务不等于模块。默认 `entities: []`，确有系统关系时才关联已有模块 ID。任务进度变化只改任务；只有接口、模块或依赖真实改变才更新图。`done` 不自动提升模块验证等级。
- Atlas 暂时不可用时，保留操作 ID/草稿和已有任务卡，继续已明确授权的计算或写作；在下一个交接点说明同步阻塞。不要为修工具耽误求解，不覆盖他人状态，不把未确认的写入当成功。

## Agent 的短路径

从仓库根目录执行，尖括号为本人实际值；私有状态在所有 Git 工作区外。命令适用于已初始化、授权的协作，不能代替首次身份核对。

```sh
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "<PRIVATE_DIR>" --mode board --assignee "<本人账号>" --status todo --limit 20 --max-bytes 12000
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "<PRIVATE_DIR>" --mode board --target "<task-id>" --detail full
node .agents/skills/system-atlas/bin/system-atlas.mjs team state --state "<PRIVATE_DIR>"
```

第一条是待办入口，不包含 doing/review；恢复工作时按需要改状态筛选。首次交接才读 manifest，随后从自己负责的看板页开始。只在准备编辑时读目标完整任务及版本，不反复读全图。目标 ID 可能同时匹配任务和模块，检查返回记录的 `type` 和准确 ID。

读取的解释：

- `connection: local-accepted-snapshot`：成员本地已验签缓存，不证明运行中的 serve 在线；`lastSync: null` / `syncFailure: null` 也不证明最新同步成功。需要新版本时，已有 serve 会同步；必要时执行一次 `team sync --state "<PRIVATE_DIR>"`，再回读目标。当前服务诊断可看本人本地 `/api/team`，不要公开 session 文件或 token。
- `connection: live`：连到了本机权威服务，不证明远端成员已经回读。`offline-accepted-snapshot`：队长服务不可达，读到旧的已确认快照，不能作为在线编辑依据。
- 分页看 `complete` 和 `page.hasMore`；有下一页时沿用相同筛选、返回的 `cursor` 和 `page.next`（CLI `--cursor` / `--page`）。列计数是整个筛选结果的计数，不是当前页条数。
- 成员字段版本用 `fieldVersions["task:<task-id>:<field>"]`，不能拿总 cursor 替代。`taskGrants` 决定能改哪些任务字段。需要组合图与任务时固定同一 cursor；版本缺失就重新读取，不能猜为 0。

成员把实际版本填入 JSON 文件，再用 `team request --state "<PRIVATE_DIR>" --payload change.json`：

```json
{
  "requestId": "alice-fit-review-unique-id",
  "changes": [
    {"operation":"task.set","taskId":"fit","field":"status","expectedVersion":16,"value":"review"},
    {"operation":"task.set","taskId":"fit","field":"deliverables","expectedVersion":4,"value":["<实际PR链接与复现记录>"]}
  ]
}
```

以上 ID/版本都是示例，不直接照发。一次提交相关字段；不要为 status 与 deliverables 分两次请求。队长使用 `task "<LEADER_DIR>/model.json" --payload change.json`，payload 为 `operationId / expectedCursor / action / taskId / patch`，与成员的字段级 payload 不同，见 [task-board](../.agents/skills/system-atlas/references/task-board.md)。

提交后在下一次正常同步后读 `team state`，按 **requestId** 找 outbox 中对应 `receipt`，再读目标任务；outbox 包含历史条目，只有 `receipt: null` 才是尚未确认。`team request` 成功是本地签名/排队，`sync` 的 `submitted` 是上传数量，都不是队长 accepted，更不是模型验证。

- `accepted`：回读任务值和 cursor，核对提交意图；计算/结果验收另外记录。
- `conflict`：重读相关字段，保留别人更新，重新决定内容，以新 ID 提交新意图。
- `forbidden`：说明缺少哪项授权，停止该写入，不绕过策略。
- 结果未知：先检查回执；确需重试时用同一 ID、同一 payload。不要连续生成新 ID。两次正常同步仍没有回执时报告一次阻塞，保留请求继续做已授权工作，不忙等；这不是超时自动判失败。

典型状态更新只需“读目标及版本 → 一次写入 → 回执和目标回读”。这是操作预算而非协议上限；缓存构造仍有本机处理成本，实际 token/耗时依客户端、历史长度和网络而异。

## 人的看板与收尾

四列各自纵向滚动，窄屏横向滚动到其他列。工具栏“精简视图”把卡片固定为 94px：保留标题、负责人、受阻/待处理提示，完整说明在详情里。切换记住本机偏好和各列可见任务，不改变数据。搜索/成员筛选后从该结果顶部开始；普通同步保持滚动位置。过多 Done 卡无需逐个删除，先筛选本人/关键词；正式验收记录留在 PR/结果目录。

关闭协作时提前停止新请求，先收回执或明确记录 pending，再撤权并发布、让成员只读回读、停止成员 serve，最后停止队长 serve。截止前预留同步缓冲；未知状态如实留证，不能自动续期。只停止本次进程，保留同步历史。

## Filter 策略：Human / Agent 共用

两个 Filter 按钮只改变投影，不写入模型，也不授予权限。看板预设可叠加成员/关键词，组合条件取交集；空结果不是任务消失。选择 all 清除该策略，清除筛选恢复全部任务。

| 界面 | 策略 ID | 语义 |
| --- | --- | --- |
| Board | all / active / blocked / review / unassigned | 全部 / 非 done / blocked 非空 / review / assignees 为空 |
| Canvas | all / unverified / blocked | 全部 / verification 的有效值不是 passed / 受阻任务明确关联的模块 |
| Canvas | neighbors / upstream / downstream | 选中节点加一跳邻接 / 沿存储箭头反向可达 / 正向可达，包含起点 |

Canvas 筛选限定当前视图（含已展开子图）。祖先容器按需要保留为上下文，以虚线框区分；提示显示匹配、上下文、隐藏及视图外匹配数量。视图外不等于不存在，必要时换视图/展开；不自动改变布局或打断详情草稿。上游/下游不包含隐含的父子数据流，不代表运行因果。Graph data 给出同一版本/视图/展开范围的 Agent 结果和 boundary，不能把被隐藏的关系当作不存在。

```sh
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "<PRIVATE_DIR>" --mode board --filter blocked --assignee "<本人账号>" --limit 20
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "<PRIVATE_DIR>" --mode view --view "<view-id>" --filter unverified --limit 30
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "<PRIVATE_DIR>" --mode view --view "<view-id>" --filter upstream --target "<node-id>" --limit 30
```

`--expanded`、`--cursor`、分页沿用原查询约定。`manifest.capabilities.filters` 返回可用预设；未知策略或不匹配模式报错，不静默退为全部。`--filter` 支持 board/view；其他查询策略继续使用原来的 local/reach/path。旧版客户端没有这些预设，应统一到本补丁，不能只给一方新增解释。

## 时间：记录事件，不推算实际工时

现有权威历史包含 `at`，快照包含 `committedAt`；签名回执包含 `actor`、可选 `context.agentId/sessionId`、`requestId`、`cursor` 和 `at`。回执 changes 只列字段，旧值/新值需结合相邻已确认快照，不能从 receipt 自行编造。Session 标识用不含凭据的短标识，不填 session URL。缺失的 actor/session 记为未知，不能追认成某位队员。

只在开始、受阻、交付、验收等实际交接点维护任务。事件时间表示权威接受时刻；离线排队会延迟，成员实际操作时间未知。拒绝回执不是状态变更。doing→review 的间隔可称“状态停留时间”，包含等待、暂停、并行工作；不能称 Agent 实际耗时，也不能以改动次数代表做了多少有效工作。

目前没有可靠的逐 Agent / Session 工时统计。本次不增加后台计时器或 Timeline 新界面。后续若确有复盘需求，可先只读投影现有事件，以任务/参与者筛选；不需要让 Agent 为计时持续发请求。

## 可扩展性约束（设计意图，尚未实现）

`todo / doing / review / done` 应是默认流程预设，而非永远固定的任务类型。未来让任务引用可复用的流程定义（稳定状态 ID、名称、顺序及明确规则）；不同任务类型可用不同预设。Human 与 Agent 同读定义，任务到模块的关联独立保存。扩展时需迁移与版本协商，并明确删列时现有任务去向；不能只新增网页列或用列名猜规则。本次不新增状态/调度引擎，避免比赛中引入协议升级和维护负担。
