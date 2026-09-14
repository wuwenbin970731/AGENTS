# AGENTS Core Repository Guidelines

本仓库是个人 Agent 工作流的规则、Task Runtime、Skill 和项目初始化源。通用候选规则保存在 `GLOBAL_AGENTS.md` 与 `PROJECT_AGENTS.md`；本文件只约束仓库自身维护。

## 仓库职责

- `GLOBAL_AGENTS.md`：用户级全局规则源；首次项目接入和后续更新时由合并工作流调用同步器，不由项目初始化器直接复制。
- `PROJECT_AGENTS.md`：新项目 `AGENTS.md` 的初始化源。
- `TASK_*.md`：新项目 `.tasks/` 中对应文件的权威模板源。
- `skills/task-runtime/`：Task 触发、渐进加载协议及 `taskctl` 权威实现。
- `scripts/init_project.py`：新项目首次初始化器。
- `scripts/sync_global_agents.py`：用户级 `AGENTS.md` 的受管块安装与安全更新器。
- `.tasks/`：本仓库自身的 Task Runtime 和任务实例。

## Task 路由

- `light` 工作不扫描 `.tasks/`。
- `tracked` 或 `rigorous` 工作使用 `task-runtime` Skill 和 `.tasks/bin/taskctl`。
- 发现时只读 Meta；确定当前任务后只读入口；资源按 Context Map 显式逐个读取，不递归展开。
- 其他 Task 默认只读 Meta。使用 revision 受控写入，冲突时重新读取并合并。
- 详细协议只在修改 Task schema、加载行为、迁移或结构不清时读取 `.tasks/TASK_WORKFLOW.md`。

## 修改约束

- 修改根目录 `TASK_WORKFLOW.md`、`TASK_TEMPLATE.md` 或 `TASK_ITERATION_TEMPLATE.md` 时，同步更新 `.tasks/` 中的自用副本；测试要求字节一致。
- 修改 `taskctl` 时只编辑 `skills/task-runtime/scripts/taskctl.py`；`.tasks/bin/taskctl` 是本仓库使用的薄包装器，初始化器会把 Python 实现安装为目标项目的可执行文件。
- Skill 保持简洁；完整 schema 和协议放在 `skills/task-runtime/references/`，不要在 `SKILL.md` 重复。
- 初始化器默认只输出计划；`--apply` 还必须带回用户 Review 过的 `--approve-plan` 摘要。不得覆盖已有不同内容，不得接管未知 `.tasks/`。
- 全局规则同步器只管理带哈希的 Core 受管块；本机扩展必须放在块外，旧文件迁移时必须显式指定保留边界；实际写入同样要求已 Review 的计划摘要。
- 首次初始化和后续项目更新都必须把系统级与项目级 dry-run 合并展示，等待一次明确 Review；无冲突不构成自动应用授权。
- 新增可执行行为时优先使用 Python 标准库并添加自动化测试。
- 不写入私人路径、凭据、内部主机或单一业务项目事实。

## 验证

修改后运行：

```bash
python3 -m unittest discover -s tests -v
python3 "${TRAE_HOME:-$HOME/.trae}/skills/.system/skill-creator/scripts/quick_validate.py" skills/task-runtime
.tasks/bin/taskctl doctor
git diff --check
```

如果 Skill 校验器环境缺少 `PyYAML`，在临时目录安装验证依赖，不把它加入本项目运行依赖。提交前检查 Git 状态、可执行位、模板同步和初始化器的 dry-run 输出。未经用户明确要求，不提交或推送。
