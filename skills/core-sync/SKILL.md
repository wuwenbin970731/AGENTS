---
name: core-sync
description: Batch-update AGENTS Core consumers from an environment-local repo registry, with parallel Orca Subtasks, pinned Core revisions, combined system/project Review, and drift checks. Use to preview, apply approved changes, or resume a batch from any downstream repo; each local or SSH environment runs independently.
---

# Core 批量同步

使用 `task-runtime` 管理 Task、`task-orchestration` 管理 Orca worker；本 Skill 连接配置、固定源版本和 README 的已有项目更新协议。首次使用或恢复时读取 [references/workflow.md](references/workflow.md)。不替换项目级三方语义合并，不把初始化器当更新命令。

1. 在实际执行环境读取 `~/.config/agents-core/repos.json`，或明确指定配置；本地与 SSH 各自发起。参考 [references/config.example.json](references/config.example.json)，不复制其中的占位路径或擅自创建用户配置。所有命令必须在该环境执行。
2. 运行 `scripts/core_sync.py inspect`。默认选取全部 enabled 项目，包括已登记的发起仓库；允许 `--repo <id>` 子集。Agent 未指定时在 prepare 前选择一次（可用 --agent 本轮覆盖，不必修改配置）；无需逐 repo 重复询问。
3. 控制工作区必须先按 README 完成系统级/项目级联合 dry-run Review 和首次安装；工具不自动初始化。运行 `prepare` 刷新 origin/main、固定正式 SHA、创建干净源快照和共享控制 Task/Subtasks。禁止从 dirty 工作树或失败缓存回退。此命令只准备批次，不修改真实系统级/下游目标。
4. 展示 prepare 生成的中文执行树、对应 schema 2 计划、目标与并发上限，获得编排批准后再启动 worker。`registry:<id>` 是稳定配置引用，实际 Orca workspace/host 要从冻结路径在当前环境解析核对，不能直接当作 CLI selector。记录编排批准、计划摘要及真实绑定。遵守 max_parallel；planctl 返回候选不代表可以忽略并发上限。
5. 各 repo 一个 Subtask，先并行预览：读取固定快照 README“Core 更新后同步已有项目”完整协议，使用各项目自身清单作为 base；运行 `preview` 获取文件级比较，再由 worker 补齐语义差异、具体补丁、保留边界与验证计划。共享系统级目标只由协调者统一 `preview-global`，项目 worker 不写它们。所有预览均不写目标。
6. 所有目标已预览或明确阻塞后运行 `review`，合并展示系统级/项目级具体提案及 review_digest。等待用户明确批准本轮选集；即使无冲突也不自动应用。编排批准、内容批准和最终验收分别记录。
7. 用 `approve` 固定批准范围与依据；系统级先 `gate-global`，再用固定快照同步器和获批 plan_digest 应用，随后 `record-global` 校验实际结果。项目先 `gate`，仅对返回的 approved_files 语义合并。任何输入漂移或不明回执先恢复/重新 Review，不重复启动或直接覆盖。
8. 同一 Subtask 分阶段续跑，优先复用已有 Orca 实例。预览只回报里程碑并等待批准，不能据此完成整个同步 Subtask。无须强迫未批准部分应用；部分批准必须明确保留未完成项。
9. 合并与验证成功且全部必要变化已获批准时才能推进安装清单；部分文件批准时遵守 manifest_advance_allowed，不伪造新基线。按固定 README 运行验证，用 record-project 记录实际变化、保留、失败、证据；不自动暂存/提交/推送。用户拒绝或不可完成的目标保留为未完成，不假报成功。
10. 遵循 Orca 的唤醒/消息/恢复协议，不轮询。批次结束先核对 worker 实际停止状态，再 close 登记；close 本身不终止 Agent。用 Task revision 写入收尾状态，提示新会话加载更新后的规则。

面向用户尽可能用中文。共享状态存控制工作区忽略的私有目录；Task 只记录稳定 ID 和脱敏摘要，不写私人路径、凭据、内部主机或整段含密钥回执。脚本只校验本地记录一致性，不能证明用户确实批准、Orca 已启动、语义合并正确或测试实际成功。
