# System Atlas 0.5.0 项目接入

安装位置：`.agents/skills/system-atlas/`。固定上游提交 `fc258c92d12d36bc9fbbabe0713056958b6cc7e2`，版本来自 SKILL.md、package.json、skill-release.json；原安装 243 文件的上游哈希保存在 [system-atlas-install.json](system-atlas-install.json)。本分支的本地补丁覆盖清单另见 `system-atlas-windows-patch.json` 和 `system-atlas-competition-patch.json`，不改写原清单。保留 MIT LICENSE 和 Archify 归属，不自动追随 main。

## 本次更新

0.4 的队长权威模型、成员签名请求、字段权限、冲突回执继续保留。0.5 增加共享任务看板：创建/修改/删除/恢复任务、分配成员标签、关联零个或多个模块、状态与交付物，以及成员的明确任务字段授权。Human Board 与 Agent board 查询来自同一已确认模型。

任务是独立集合，任务不等于模块；`entities: []` 是合法独立任务。`assignees` 不是权限、在线状态或独占锁；`done` 不改变模块的设计/实现/验证/运行成熟度。该 Skill 不自动启动队员 Agent，不执行任务调度。队员按本人授权主动读任务、执行、交付，Mailbox 负责通知和代码交接。

## 使用

Node.js 18+ 为上游要求，本项目统一 Node.js 22+。原生 Windows 的目录 fsync EPERM 已在 PR #11 的专用补丁中处理，真实 Windows 队员完成启动及签名同步；文件 fsync 保留，目录项断电耐久性不能与 POSIX 等同，完整 Windows 回归仍有 12 项 symlink 权限失败。见 [平台边界](rehearsal/WINDOWS_COMPAT.md)。本分支基于该补丁，不代表 main 或队员本机已更新。队友克隆后显式读取 [SKILL.md](../.agents/skills/system-atlas/SKILL.md)，其他 Agent 也可读取。需要依赖时：

```sh
npm ci --ignore-scripts --prefix .agents/skills/system-atlas
node .agents/skills/system-atlas/bin/system-atlas.mjs validate tests/rehearsal/system.json --repo-root . --json
node .agents/skills/system-atlas/bin/system-atlas.mjs preview .agents/skills/system-atlas/examples/math-modeling.system.json --repo-root .agents/skills/system-atlas
```

打开终端打印的本机 URL，结束 Ctrl-C。上游数学建模示例中的人员/任务/完成进度均为演示，不能当本队结果；本项目预演模型另存于 `tests/rehearsal/system.json`，初始任务为空。

## 团队启用与真机联测

先读 [collaboration.md](../.agents/skills/system-atlas/references/collaboration.md) 与 **[task-board.md](../.agents/skills/system-atlas/references/task-board.md)**，后者包含 0.5 新增的 `task.set` 和 taskGrants。参与者都升级至 0.5，0.4 校验器会拒绝带 tasks 的模型。

用户已指定由自己（NikolaStarx）当联测队长。预演 `r20260923-0011-35c5` 已结束，预演写权限已撤销、队長服务已停止，历史保留。不要把已结束预演当成正式部署。正式协作按 [Agent 短指南](ATLAS_AGENT_GUIDE.md) 维护，并按本人授权单独建立正式身份/权限范围。

私有目录必须位于所有 Git 工作区之外。队长初始化时复制模型，此后权威源为 `LEADER_DIR/model.json`；仓库中的原始模型和 Git 同步分支都是不同的对象，不得把远端快照 pull 回权威源。只在 `serve` 活跃时持续同步；不同设备可能短暂持有不同 cursor，应在相同版本和范围比较。成员身份、邀请和密钥信任需要本人核对。

## 验证和后续更新

2026-09-22 本机 Node.js 22.22.3：`npm ci --ignore-scripts` 成功，`npm test` **91/91** 通过。另用项目预演脚本调用实际 CLI，验证本地 bare Git 上的任务创建、授权、签名请求、冲突、原子拒绝及同版本回读。详细范围见 [预演准备验证](rehearsal/VALIDATION.md)。

上述是原安装时的机制验证。后续真实 Windows/Mac 签名同步、越权原子拒绝、冲突及人工拖动的同版本回读已有 [PR #12 报告](https://github.com/huaweibei123/huaweicup2026/pull/12)；F3 与最后 review/撤权成员回读未完成。本分支密集看板/缓存提示的范围见 [验证报告](ATLAS_STABILITY_VALIDATION.md)。上游附带的 verification 文档只代表上游报告，不当作本次验收。

更新应在任务分支核对上游提交和差异、替换完整 Skill、更新哈希清单，并通过 PR 汇合。本地修复须保留原清单，另记逐文件原哈希/补丁哈希，并纳入预检；不能将未登记的源码改动当作原版。CI 见 [.github/workflows/system-atlas.yml](../.github/workflows/system-atlas.yml)，本次项目适配内容在 Skill 外。
