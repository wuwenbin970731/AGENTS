---
task_schema: 4
task_id: 2026-09-14-190000-progressive-task-runtime
iteration: F001
status: completed
created_at: 2026-09-14T20:18:00+08:00
updated_at: 2026-09-14T20:25:00+08:00
completed_at: 2026-09-14T20:25:00+08:00
trigger: user-review
---

# F001：系统级 AGENTS 同步

任务入口：[../TASK.md](../TASK.md)

## 本轮边界

- 触发：用户指出系统级 `AGENTS.md` 也应随 Core 更新。
- 目标：为用户级全局规则提供独立、可审计、保留本机扩展的同步入口，并迁移当前实际生效文件。
- 范围：全局同步脚本、README、仓库维护规则、自动化测试和当前 `~/.codex/AGENTS.md`。
- 非目标：将全局规则混入每个下游项目初始化；自动更新已有下游项目；提交或推送 Core。

## 事实与决策

- 实际生效的全局文件为 `~/.codex/AGENTS.md`，原文件包含旧 Core 模板和独立的 `.TRAE` 本机规则。
- 项目初始化器仍只写目标项目目录；全局文件由 `scripts/sync_global_agents.py` 独立管理。
- 同步边界采用带源提交、dirty 标记和内容哈希的 `agents-core-managed` 块；块外内容逐字保留。
- 未受管旧文件默认拒绝覆盖。一次性迁移必须通过 `--adopt-local-tail-from` 指定唯一标题边界。
- 已受管块若发生手工编辑且内容哈希不匹配，同步器拒绝覆盖，要求语义合并。
- 写入现有文件前创建权限为 `0600` 的时间戳备份，再原子替换目标。

## 实际改动

| 文件或目标 | 改动 | 作用 |
|---|---|---|
| `scripts/sync_global_agents.py` | 新增 dry-run、受管块迁移、哈希检查、备份和原子写入 | 安全维护系统级规则 |
| `README.md` | 增加系统级同步命令、迁移规则和 Agent 提示词 | 后续会话可自行安装或更新全局规则 |
| `AGENTS.md` | 补充同步器职责和维护边界 | 约束 Core 自身维护 |
| `tests/test_task_runtime.py` | 新增 4 个全局同步场景 | 覆盖首次安装、本机扩展、篡改拒绝和旧文件迁移 |
| `~/.codex/AGENTS.md` | 旧模板迁移为 Core 受管块，保留 `.TRAE` 章节 | 让新会话实际采用 schema 4 渐进披露规则 |

## 执行与验证

| 时间 | 命令或操作 | 结果 |
|---|---|---|
| 2026-09-14 | `python3 scripts/sync_global_agents.py --adopt-local-tail-from '# .TRAE 目录的使用规则'` | dry-run 为 `migrate`，识别需保留 608 字节本机内容 |
| 2026-09-14 | 同命令增加 `--allow-dirty-source --apply` | 成功迁移并在 `~/.codex/.agents-core-backups/` 创建备份 |
| 2026-09-14 | 再次运行全局同步器 dry-run | `unchanged`，具备幂等性 |
| 2026-09-14 | 比较受管正文、哈希和新旧本机尾部 | Core 正文完全一致；`.TRAE` 正文完整保留，旧同步标记前一个分隔空行被首版迁移器规范化 |
| 2026-09-14 | `python3 -m unittest discover -s tests -v` | 17 个测试全部通过 |
| 2026-09-14 | `quick_validate.py skills/task-runtime` | `Skill is valid!` |
| 2026-09-14 | `.tasks/bin/taskctl doctor` | 1 Task，0 error，0 warning |
| 2026-09-14 | `git diff --check` | 通过 |

## 收束

- 当前系统级文件已经更新，但因为 Core 尚未提交，同步元数据诚实记录 `source_dirty: true` 和精确内容哈希。
- 迁移后已修正脚本，使后续一次性迁移按原始字节保留本机章节，并增加覆盖末尾空白的回归断言；当前文件只存在上述非语义空行差异。
- 用户 Review 并提交 Core 后，再运行一次 `python3 scripts/sync_global_agents.py --apply`，即可将全局文件刷新为可复现的干净提交基线。
- 本轮未提交、未推送仓库。
