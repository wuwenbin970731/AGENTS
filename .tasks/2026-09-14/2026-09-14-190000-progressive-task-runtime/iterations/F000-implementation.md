---
task_schema: 4
task_id: 2026-09-14-190000-progressive-task-runtime
iteration: F000
status: completed
created_at: 2026-09-14T19:00:00+08:00
updated_at: 2026-09-14T19:40:00+08:00
completed_at: 2026-09-14T19:40:00+08:00
trigger: initial
---

# F000：实现渐进式 Task Runtime

任务入口：[../TASK.md](../TASK.md)

## 本轮边界

- 触发：用户确认 `.tasks/` 目录和脚本优先方案，并授权文档与代码实现。
- 目标：完成第一版可运行实现与端到端验证。
- 范围：本仓库 Task 规则、Skill、CLI、初始化器、测试和文档。
- 非目标：修改或迁移其他项目。

## 事实与决策

- 初始状态：仓库只有六份 Markdown 模板，Task schema 为 3。
- 已确认事实：普通恢复约定读取活动 iteration；模板没有 Meta 搜索、session binding 或 revision 写冲突协议。
- 必须保持：初始化时保护项目已有规则，不自动覆盖或提交。
- 本轮决定：Python 标准库实现，避免第三方依赖；运行时安装到 `.tasks/bin/taskctl`；Skill 安装到项目 `.agents/skills/task-runtime/`。

## 实际改动

| 文件与符号 | 改动 | 作用 |
|---|---|---|
| `skills/task-runtime/` | 新增 Skill、协议、schema 和 CLI | 触发与执行渐进式 Task 工作流 |
| `.tasks/` | 新增本仓库运行时、模板和真实 Task | 让仓库自身采用 schema 4 |
| `scripts/init_project.py` | 新增只读计划和显式应用 | 安全初始化新项目 |
| `AGENTS.md` 和规则模板 | 统一渐进加载、写入和维护规则 | 让本仓库和新项目遵循同一协议 |
| `tests/test_task_runtime.py` | 新增 13 个端到端场景 | 覆盖初始化、披露边界、写冲突、状态目录降级、Meta 约束和兼容性 |
| `README.md` | 新增 Agent 可复制的初始化、更新、启用和 Markdown 分发说明 | 让后续会话可仅靠仓库文档完成接入或同步 |

## 执行与验证

| 时间 | 目录 | 命令或操作 | 结果 | 证据或产物 |
|---|---|---|---|---|
| 2026-09-14 | repo | `python3 -m py_compile skills/task-runtime/scripts/taskctl.py` | pass | Python 语法检查通过 |
| 2026-09-14 | repo | `python3 -m unittest discover -s tests -v` | pass | 13 个测试全部通过 |
| 2026-09-14 | repo | `quick_validate.py skills/task-runtime` | pass | Skill is valid |
| 2026-09-14 | repo | `.tasks/bin/taskctl doctor` | pass | 1 Task，0 error，0 warning |
| 2026-09-14 | repo | `git diff --check` | pass | 无空白错误 |

- 验证结论：初始化 dry-run/apply/幂等、拒绝未知 `.tasks/`、Meta-only 搜索、最多八个候选、Context Map 显式读取、防路径逃逸、完整入口写入、revision 冲突、session staleness、schema 3 读取兼容和模板一致性均通过。
- 未覆盖边界：真实第三方项目的语义升级仍需按 README 走人工 base/ours/theirs 评审；本版初始化器只负责首次无冲突安装。
- 大型证据：不适用。

## 收束

- 写回 TASK 的当前结论：schema 4、CLI、Skill、初始化器、规则文档和自动化测试均已完成。
- 最后完成：仓库自治理规则和最终验证。
- 尚未验证：无当前实现阻塞项。
- 下一步：由用户 Review 工作区差异；确认后再决定提交或继续增强更新器。
- 完成时间：2026-09-14T19:40:00+08:00
