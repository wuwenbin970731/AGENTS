---
task_schema: 4
task_id: 2026-09-14-190000-progressive-task-runtime
iteration: F002
status: awaiting_user
created_at: 2026-09-14T20:28:00+08:00
updated_at: 2026-09-14T20:37:00+08:00
completed_at: null
trigger: user-review
---

# F002：系统级与项目级合并 Review Gate

任务入口：[../TASK.md](../TASK.md)

## 本轮边界

- 触发：用户要求首次项目初始化和后续项目更新都同时处理系统级 `AGENTS.md`，但所有目标必须先 dry-run，待 Review 后再实际更新。
- 目标：把这项要求落实到 README 主流程和可执行脚本，而非只依赖 Agent 自觉。
- 范围：项目初始化器、全局同步器、README、全局/项目规则源、测试和 Task 记录。
- 非目标：实现已有项目的自动三方合并脚本；未经 Review 更新当前系统级文件。

## 事实与决策

- 首次初始化和后续更新都是双目标流程：系统级 Core 受管块，以及当前项目的规则、Task Runtime 和 Skill。
- 两部分必须先同时分析，合并为一份 Review 提案；无冲突也不自动写入。
- 一次确认可以批准两部分或其中一部分，但只对本轮具体计划有效。
- `init_project.py` 和 `sync_global_agents.py` 的 dry-run 都输出 `plan_digest`。
- `--apply` 必须携带 `--approve-plan <digest>`；摘要绑定源内容、目标状态、目标路径、参数、动作和预期结果。
- Review 后源或目标变化会生成不同摘要，旧确认被拒绝。
- 已有项目更新仍由 Agent 进行 base/ours/theirs 语义合并；全局部分使用同步器摘要。

## 实际改动

| 文件 | 改动 | 作用 |
|---|---|---|
| `scripts/init_project.py` | 增加计划摘要和强制 `--approve-plan` | 防止首次初始化绕过 Review 或使用过期计划 |
| `scripts/sync_global_agents.py` | 增加计划摘要和强制 `--approve-plan` | 防止系统级规则绕过 Review 或使用过期计划 |
| `README.md` | 重写首次初始化、已有项目更新和快速开始流程 | 系统级与项目级统一 dry-run、合并 Review、确认后应用 |
| `GLOBAL_AGENTS.md` | 加入跨项目的双目标 Review 原则 | 让新会话默认遵守 |
| `PROJECT_AGENTS.md` | 加入项目接入和更新的双目标 Review 规则 | 下游项目保留最低安全约束 |
| `AGENTS.md` | 加入 Core 维护时的 Review gate 不变量 | 防止未来回退为直接 apply |
| `tests/test_task_runtime.py` | 总场景增至 22 个 | 覆盖缺失摘要、错误摘要、Review 后目标变化和 README 协议 |
| `README.md` 的可复制 Prompt | 固定 Core URL，并去除 Core 路径占位符 | 首次初始化和已有项目更新可直接复制使用 |

## 验证与当前 Review 项

| 检查 | 结果 |
|---|---|
| `python3 -m unittest discover -s tests -v` | 22 个测试全部通过 |
| Python 语法检查 | 通过 |
| `quick_validate.py skills/task-runtime` | `Skill is valid!` |
| `.tasks/bin/taskctl doctor` | 1 Task，0 error，0 warning |
| `git diff --check` | 通过 |
| 提交前系统级同步 dry-run | action=`update`，未写入；该 dirty-source 摘要仅用于验证 gate，不用于提交后应用 |

系统级计划的内容影响：

- 更新 Core 受管块，使其与当前 `GLOBAL_AGENTS.md` 一致。
- 新增规则：使用 AGENTS Core 首次初始化或更新项目时，系统级与项目级必须同时 dry-run、合并展示；无冲突也等待 Review；只应用获批部分；输入变化时重新预览。
- 保持受管块外现有 `.TRAE` 本机规则不变。
- 应用时会再次备份当前系统级文件并原子替换。
- Core 提交会改变 `source_commit` 和 `source_dirty`，因此必须在推送完成、工作树干净后重新 dry-run，再将新的可复现摘要交给用户 Review。提交前摘要不得复用。

## 等待用户

- 当前没有应用系统级计划。
- 用户已要求提交并推送 Core；完成后重新生成基于干净提交的系统级摘要，再等待用户 Review。
