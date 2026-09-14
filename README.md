# AGENTS Core

这是一个面向个人 Agent 工作流的核心仓库，用于安全初始化新项目，并为长任务提供可执行的渐进式上下文管理能力。它不再只是 Markdown 模板集合：仓库包含项目规则、Task schema、`task-runtime` Skill、`taskctl` CLI、初始化脚本和自动化测试。

设计重点是控制上下文边界。Agent 搜索任务时只看到 Meta，确定当前 Task 后只读取其入口，详细设计、运行手册、决策、迭代和证据都必须按明确条件逐个加载。

## 仓库内容

| 路径 | 用途 | 初始化目标 |
|---|---|---|
| `AGENTS.md` | 本仓库自己的维护规则 | 不复制 |
| `GLOBAL_AGENTS.md` | 跨项目最小协作原则 | 用户级 `AGENTS.md` 的 Core 受管块 |
| `PROJECT_AGENTS.md` | 项目规则模板 | `<project>/AGENTS.md` |
| `TASK_WORKFLOW.md` | Task 完整协议 | `<project>/.tasks/TASK_WORKFLOW.md` |
| `TASK_TEMPLATE.md` | schema 4 Task 入口模板 | `<project>/.tasks/TASK_TEMPLATE.md` |
| `TASK_ITERATION_TEMPLATE.md` | 可选过程证据模板 | `<project>/.tasks/TASK_ITERATION_TEMPLATE.md` |
| `skills/task-runtime/` | Agent Task Skill 与协议引用 | `<project>/.agents/skills/task-runtime/` |
| `skills/task-runtime/scripts/taskctl.py` | Task CLI 权威实现 | `<project>/.tasks/bin/taskctl` 和 Skill scripts |
| `scripts/init_project.py` | 新项目初始化器 | 不复制 |
| `scripts/sync_global_agents.py` | 用户级规则安装与更新器 | 不复制，直接从 Core 运行 |
| `.tasks/` | 本仓库自己的 Task Runtime 和真实 Task | 不作为模板整体复制 |

仓库文件是规则和实现源，不构成覆盖目标项目已有文件的授权。

### 系统级（用户级）AGENTS.md

首次初始化项目和后续同步已有项目时，都必须把系统级规则纳入同一轮更新。项目初始化器本身仍不越界修改用户目录，而是由工作流同时调用全局同步器和项目级工具，汇总两部分 dry-run 后交给用户一次 Review。未获得对本轮具体计划的确认前，即使没有冲突也不得写入。

Codex 的默认系统级目标为 `${CODEX_HOME:-$HOME/.codex}/AGENTS.md`，其他客户端或自定义位置必须显式传入 `--target`。全局同步器可单独用于排查，但不应在项目接入或更新时被遗漏。

```bash
# 只预览，不写入
python3 scripts/sync_global_agents.py

# 用户 Review 并确认上一步输出后，带回原计划摘要应用
python3 scripts/sync_global_agents.py \
  --apply \
  --approve-plan <global-plan-digest>
```

同步器只替换 `agents-core-managed` 受管块。本机长期规则放在该块之外，会在后续更新中原样保留；如果受管块被手工修改且与记录哈希不一致，同步器会拒绝覆盖。写入现有文件前会备份到目标目录下的 `.agents-core-backups/`，并使用原子替换。

首次遇到没有受管块的旧全局文件时，同步器默认报冲突。Review 旧内容后，显式指定需要保留的本机章节标题完成一次性迁移：

```bash
python3 scripts/sync_global_agents.py \
  --adopt-local-tail-from '# 本机自定义规则'
python3 scripts/sync_global_agents.py \
  --adopt-local-tail-from '# 本机自定义规则' \
  --apply \
  --approve-plan <global-plan-digest>
```

该参数会用当前 `GLOBAL_AGENTS.md` 替换标题之前的旧模板，只保留从指定标题开始的内容，因此必须先检查预览，并确认标题是唯一、准确的语义边界。正常维护应先提交 Core；只有明确需要试用未提交版本时才增加 `--allow-dirty-source`，同步元数据会记录 `source_dirty` 和精确内容哈希。

dry-run 输出的 `plan_digest` 绑定 Core 源内容、系统级目标当前内容、目标路径、迁移参数和预期结果。`--apply` 必须通过 `--approve-plan` 带回用户实际 Review 的摘要；Review 后任一输入变化都会产生新摘要并拒绝旧确认。确认只授权本轮这份计划，不授权未来更新。更新后的规则只对新会话完整生效。

也可以让 Agent 执行：

```text
请使用 AGENTS Core 检查当前客户端的用户级 AGENTS.md。
先读取 Core 的 README.md、GLOBAL_AGENTS.md 和 scripts/sync_global_agents.py，确认客户端实际使用的全局文件位置。
只执行 dry-run；若是未受管旧文件，先做语义检查并提出明确的本机内容保留边界，不得覆盖。
展示计划、plan_digest 和影响后停止，等待我 Review。只有我确认这份具体计划后，才能用同一 plan_digest 执行 --apply，并检查备份、最终 diff 和同步元数据。
```

## 推荐：让 Agent 直接完成接入和更新

日常使用不要求记住本仓库的文件映射，也不需要替换 Core 地址。下面的 Prompt 已固定使用 `https://github.com/wuwenbin970731/AGENTS.git`；Agent 应通过已认证 Git 获取临时检出，并固定 `origin/main` 提交。

### 首次初始化一个新项目

在目标项目会话中发送：

```text
请使用 AGENTS Core 初始化当前项目。

AGENTS Core：https://github.com/wuwenbin970731/AGENTS.git
目标项目：当前工作区根目录

请执行以下流程：
1. 确认目标项目根目录、Git 状态、当前生效的项目级 AGENTS.md / AGENTS.override.md，以及当前客户端实际使用的系统级 AGENTS.md。
2. 使用当前已认证 Git 将上述 AGENTS Core 检出到安全的临时目录，fetch origin，并将 origin/main 的完整 SHA 固定为本次源版本；网络或认证失败时停止，不使用缓存版本。
3. 阅读 Core 的 README.md、GLOBAL_AGENTS.md、PROJECT_AGENTS.md、scripts/sync_global_agents.py 和 scripts/init_project.py，确认系统级与项目级目标、安装文件和安全边界。不要读取 Core 自身 .tasks 下的任务正文。
4. 使用临时检出中的脚本同时执行两个 dry-run：运行 `scripts/sync_global_agents.py` 检查当前客户端实际使用的系统级目标，运行 `scripts/init_project.py` 并以当前工作区根目录作为项目参数。不得传 `--apply`。
5. 将两个结果汇总成一份 Review 提案，分别列出系统级受管块和项目级文件的创建、更新、不变、冲突、本机保留内容、风险及各自 `plan_digest`。即使两边都无冲突，也必须停止并等待我明确确认。
6. 若全局文件未受管，先提出准确的本机内容保留边界并重新 dry-run；若项目已有不同内容或未知 `.tasks/`，先给出保留项目规则的语义合并提案。不得直接覆盖。
7. 只有我确认本轮具体提案后，才应用获批部分：全局同步使用 `--apply --approve-plan <global-digest>`；无冲突的首次项目安装使用 `--apply --approve-plan <project-digest>`；冲突项只按确认后的语义补丁处理。任一摘要失效时重新 dry-run 和 Review，不沿用旧确认。
8. 安装后根据当前项目的真实代码、配置和文档，补充 AGENTS.md 的项目入口、测试命令、环境边界和不变量；不得从其他项目猜测。
9. 运行全局同步 dry-run确认 `unchanged`、`.tasks/bin/taskctl --version`、`.tasks/bin/taskctl doctor` 和适合本项目的最小检查。
10. 展示系统级备份与元数据、项目实际变更和 Git diff；不要自动暂存、提交或推送。提示我开启新会话。
```

所有新仓库都会先停在合并后的 dry-run Review 阶段；“没有冲突”不再构成自动写入授权。

### Core 更新后同步已有项目

在已经初始化过的目标项目会话中发送：

```text
请按照 AGENTS Core 的 README 协议更新系统级 AGENTS.md，以及当前项目中的 Agent 规则、Task Runtime 和 task-runtime Skill。

AGENTS Core：https://github.com/wuwenbin970731/AGENTS.git
目标项目：当前工作区根目录

请执行以下流程：
1. 读取当前项目 `.tasks/agent-core.json`，取得 source、source_commit 和已安装文件哈希；读取当前项目实际生效的 AGENTS.md / AGENTS.override.md，并确认当前客户端实际使用的系统级 AGENTS.md。
2. 使用已认证 Git 刷新正确的 Core 检出，并将 origin/main 的完整 SHA 固定为本次 theirs。认证、fetch 或历史提交读取失败时停止，不退回缓存或历史对话。
3. 阅读 Core 当前 README.md、GLOBAL_AGENTS.md、scripts/sync_global_agents.py 和 scripts/init_project.py 中的 COPY_MAP，确定系统级受管块、当前项目受管文件及新增文件。不要把 Core 自身的 Task 实例复制到当前项目。
4. 对系统级目标执行 `sync_global_agents.py` dry-run；同时使用 source_commit 中的项目源文件作为 base、当前项目文件作为 ours、固定的 Core 新提交作为 theirs，逐文件、逐章节进行项目级三方语义比较。不得修改任何目标。
5. 输出一份合并 Review 提案：系统级部分列出 action、本机保留内容、风险和 `plan_digest`；项目级部分列出可直接更新、本地专属修改、双方一致修改、冲突、远端新增、候选删除和保持不变项。
6. 即使系统级或项目级没有冲突，也必须等待我对本轮具体提案的明确确认。确认可以同时批准两部分，也可以只批准其中一部分；不得扩展为未来更新授权。
7. 确认后再增量应用：全局同步使用已 Review 的 `--approve-plan`；项目中 ours 等于 base 的文件可更新为 theirs，ours 独有内容保留，双方修改同一区域时语义合并，远端删除不得自动删除本地内容。禁止直接覆盖整个项目 AGENTS.md。任一输入变化时重新 dry-run 和 Review。
8. 代码和 Skill 脚本也要按清单更新并保持可执行位；新增的下游文件必须已登记在 Core 的 COPY_MAP 中。
9. 合并和验证成功后，将 `.tasks/agent-core.json` 更新到本次 theirs 提交并记录新版源文件哈希；若 Core 工作树是 dirty 状态，不得把它记录成可复现的正式同步基线。
10. 运行全局同步 dry-run确认 `unchanged`、`.tasks/bin/taskctl --version`、`.tasks/bin/taskctl doctor`、Skill 校验、`git diff --check` 和适合当前项目的测试。报告实际采用、保留和拒绝的变化，不要自动暂存、提交或推送，并提示我开启新会话。
```

当前版本没有自动覆盖式项目 updater。更新流程由 Agent 执行项目级语义比较，因为下游 `AGENTS.md` 和部分 Markdown 往往包含项目专属修改；系统级部分则由同步器生成并校验计划摘要。`scripts/init_project.py --apply` 是首次安装命令，不是已有项目的更新命令。

### 初始化或更新后开始使用 Task

规则或 Skill 更新后建议开启一个新会话，使项目 `AGENTS.md` 和 `task-runtime` Skill 被重新发现。然后可以直接发送：

```text
请使用项目内的 task-runtime 处理这个需求。
先判断它是 light、tracked 还是 rigorous。
如果需要 Task，先只搜索现有 Task 的 Meta；复用目标和完成标准相同的 Task。
没有匹配项时再创建新 Task。确定当前 Task 后只读取 TASK.md，其他资源严格按照 Context Map 按需加载。
```

恢复已有任务时发送：

```text
请使用项目内的 task-runtime 继续 Task <task-id>。
先读取它的 TASK.md 并重新核对 Git、代码、测试、日志和外部状态；不要默认读取 iterations 或 archive。只有当前动作满足 Context Map 的读取条件时，才读取对应单个资源。
```

即使 Agent 客户端没有发现项目本地 Skill，项目 `AGENTS.md` 仍保存了最小加载协议；此时可以明确要求它使用 `.tasks/bin/taskctl`。

## 快速开始

### 1. 预览系统级和新项目初始化

```bash
python3 scripts/sync_global_agents.py
python3 scripts/init_project.py /path/to/project
```

默认只输出计划，不写文件。初始化器会检查：

- 目标项目是否存在；
- `.tasks/` 是否为空或由本仓库管理；
- `AGENTS.md` 和目标文件是否已存在不同内容；
- 将创建哪些规则、模板、Skill 和脚本。

两个命令都默认只输出计划，不写文件。Agent 应把两份结果合并展示，等待用户 Review。

### 2. Review 后显式应用

```bash
python3 scripts/sync_global_agents.py \
  --apply \
  --approve-plan <global-plan-digest>
python3 scripts/init_project.py /path/to/project \
  --apply \
  --approve-plan <project-plan-digest>
```

`plan_digest` 不是永久授权令牌。它只代表一次具体 dry-run；Core 内容、目标内容、路径、参数或计划发生变化后，旧摘要会被拒绝，必须重新预览并 Review。

初始化后项目获得：

```text
project/
├── AGENTS.md
├── .agents/skills/task-runtime/
└── .tasks/
    ├── config.json
    ├── agent-core.json
    ├── .gitignore
    ├── bin/taskctl
    ├── TASK_WORKFLOW.md
    ├── TASK_TEMPLATE.md
    └── TASK_ITERATION_TEMPLATE.md
```

如果存在不同内容，初始化器返回冲突且不覆盖。已有项目应先进行后文的语义合并。初始化器不修改 `.gitignore`，也不暂存、提交或推送。

`.tasks/agent-core.json` 记录源仓库、源提交、工作树是否有未提交修改，以及每个安装文件的 SHA-256。源仓库干净时，后续更新可以通过 `source_commit` 恢复三方比较所需的 base；清单不是 Task 索引。

### 3. 验证安装

```bash
.tasks/bin/taskctl --version
.tasks/bin/taskctl doctor
```

`taskctl` 只依赖 Python 3.10+ 标准库。

## Task 存储

默认 Task 根目录为项目根目录下的 `.tasks/`，避免与业务代码常见的 `tasks/` 目录冲突：

```text
.tasks/YYYY-MM-DD/<task-id>/
├── TASK.md                    # 必需：Meta、当前契约和上下文地图
├── design/                    # 当前详细设计，按需
├── runbooks/                  # 运行与恢复步骤，按需
├── decisions/                 # 长期设计决定，按需
├── iterations/                # 单轮过程证据，按需
├── evidence/                  # 大型证据，按需
└── archive/                   # 旧原文，按需
```

新 Task 默认只创建 `TASK.md`。目录名称以 `.` 开头不会让 Git 自动忽略它；项目可自行决定是否纳入版本控制。

会话绑定和写入锁不属于 Task 内容，保存在 Git 私有目录：

```text
<absolute-git-dir>/task-state/
├── sessions/
└── locks/
```

非 Git 项目，或运行沙箱禁止写入 Git 私有目录时，自动降级到已忽略的 `.tasks/.state/`。

## 四级渐进式披露

| 层级 | 内容 | 进入条件 |
|---|---|---|
| L0 | `TASK.md` frontmatter Meta | 搜索和关联任务查询 |
| L1 | 当前任务 `TASK.md` | Task 已确定 |
| L2 | 当前设计、runbook、decision | Context Map 的读取条件匹配当前工作 |
| L3 | iteration、evidence、archive | 需要追溯或核验具体结论 |

核心约束：

- `light` 工作不扫描 Task。
- 搜索最多返回八个候选，且不读取正文。
- 读取 `TASK.md` 不代表展开其中链接。
- Context Map 必须说明每个资源保存什么、何时读取。
- 资源不会递归展开它引用的其他文件。
- 其他 Task 默认只暴露 Meta。

## `taskctl` 使用

### 发现和读取

```bash
# 默认只搜索 open Task 的 Meta
.tasks/bin/taskctl search "camera quality" --limit 8

# 单个 Task 的 Meta
.tasks/bin/taskctl show <task-id>

# 明确打开当前 Task 入口，不展开链接
.tasks/bin/taskctl show <task-id> --entry

# 只列 Context Map
.tasks/bin/taskctl context list <task-id>

# 显式读取一个已声明资源
.tasks/bin/taskctl context read <task-id> design/CURRENT.md

# 关联 Task 仍只返回 Meta
.tasks/bin/taskctl related <task-id>
```

### 创建 Task

```bash
.tasks/bin/taskctl new "模型评估修复" \
  --summary "修复评估尺寸契约并验证真实推理结果" \
  --slug model-evaluation-fix \
  --mode rigorous \
  --tag evaluation \
  --tag camera-sr
```

### 检查点更新

```bash
.tasks/bin/taskctl update <task-id> \
  --expect-revision 3 \
  --checkpoint "已完成接口修复和局部测试" \
  --next-action "运行端到端评估" \
  --verified-now
```

修改完整 `TASK.md` 时，先把入口复制到临时文件并编辑，再执行：

```bash
.tasks/bin/taskctl write <task-id> \
  --from /tmp/TASK.proposed.md \
  --expect-revision 3
```

revision 不一致时命令以退出码 `3` 拒绝覆盖。调用方必须重新读取当前入口并语义合并。

### 跨会话绑定

```bash
.tasks/bin/taskctl bind <task-id> --session <stable-session-id>
.tasks/bin/taskctl current --session <stable-session-id>
.tasks/bin/taskctl unbind --session <stable-session-id>
```

一个 Task 可以绑定多个会话；一个会话只有一个当前 Task。绑定只是本地恢复提示，不是写锁。没有稳定 session ID 时，使用明确 Task ID 或 Meta 搜索恢复。

### 结构检查

```bash
.tasks/bin/taskctl doctor
```

它会检查 schema、状态值、重复 ID、Meta 和入口预算、Context Map 资源存在性及路径逃逸。

## Task schema 4

frontmatter 是 Meta 唯一权威来源：

```yaml
---
task_schema: 4
id: 2026-09-14-190000-progressive-task-runtime
title: Task 渐进式披露
summary: "建立跨会话恢复、Meta 搜索和按需上下文加载能力"
status: in_progress
mode: rigorous
design_status: implementation_ready
tags: [agents, task-system]
checkpoint: "第一版 CLI 已完成"
next_action: "执行端到端验证"
revision: 3
created_at: 2026-09-14T19:00:00+08:00
updated_at: 2026-09-14T21:00:00+08:00
verified_at: null
parent_task: null
depends_on: []
---
```

状态定义和迁移规则见 `TASK_WORKFLOW.md`；机器执行边界见 `skills/task-runtime/references/`。

## Skill 工作方式

`task-runtime` Skill 保持精简，只包含任务路由、加载层级和写入步骤。完整协议与 schema 放在 references 中，仅在修改协议或迁移旧 Task 时加载；确定性行为全部交给 `taskctl`。

项目初始化器将 Skill 安装到：

```text
<project>/.agents/skills/task-runtime/
```

如果某个 Agent 运行环境不发现项目本地 Skill，`AGENTS.md` 中仍保留最小渐进披露协议，`.tasks/bin/taskctl` 也可直接调用。

## 更新已有项目

系统级与项目级更新必须属于同一轮 Review，但采用各自适合的执行方式：系统级受管块由 `sync_global_agents.py` 生成可验证计划；项目级文件禁止用初始化器覆盖已有不同内容，采用三方语义比较：

- `base`：上次成功同步的本仓库版本。
- `ours`：项目当前本地文件。
- `theirs`：本仓库固定提交中的新版本。

推荐流程：

1. 使用已认证 Git 刷新本仓库并固定 `origin/main` 完整 SHA。
2. 读取系统级目标，以及项目实际生效的规则、Task 模板、Skill 和脚本。
3. 对系统级目标运行 dry-run；项目级按文件和语义比较 base、ours、theirs。
4. 合并展示系统级与项目级的拟新增、修改、删除、冲突、保持项、风险和计划摘要，然后停止等待 Review。
5. 获得本轮明确确认后，只应用获批部分；全局使用已确认摘要，项目使用局部补丁并保留专属规则。
6. 若目标或源在等待期间变化，重新 dry-run 和 Review，不使用旧确认。
7. 运行全局幂等检查、`taskctl doctor`、自动化测试和项目所需检查。
8. 只有全部成功后才更新项目中的同步来源元数据。

远端删除不得自动删除本地规则；降低安全、验证或用户确认要求的变化必须单独确认。

### 上游新增 Markdown 如何进入下游

并非 Core 中的所有 Markdown 都会复制给下游。同步范围由 [scripts/init_project.py](scripts/init_project.py) 中的 `COPY_MAP` 明确定义：

| Core 内容 | 下游位置 | 是否同步 |
|---|---|---:|
| `PROJECT_AGENTS.md` | `AGENTS.md` | 是，需保护项目定制 |
| `TASK_WORKFLOW.md` | `.tasks/TASK_WORKFLOW.md` | 是 |
| `TASK_TEMPLATE.md` | `.tasks/TASK_TEMPLATE.md` | 是 |
| `TASK_ITERATION_TEMPLATE.md` | `.tasks/TASK_ITERATION_TEMPLATE.md` | 是 |
| `skills/task-runtime/**` | `.agents/skills/task-runtime/**` | 是 |
| `taskctl.py` | `.tasks/bin/taskctl` | 是 |
| `GLOBAL_AGENTS.md` | 用户级规则的 Core 受管块 | 不复制到项目；同轮调用 `sync_global_agents.py` |
| Core 的 `README.md`、测试和自身 `.tasks` | 无 | 否 |
| 下游 `.tasks/YYYY-MM-DD/...` | 保持在下游 | 永不由 Core 覆盖 |

如果以后在 Core 新增一个需要安装到下游的 Markdown，必须同时：

1. 将源路径和下游目标路径加入 `COPY_MAP`。
2. 在本 README 的仓库内容或文件映射中说明用途。
3. 为首次安装、已存在冲突和后续更新补测试。
4. 更新后让下游 Agent 按上面的 base/ours/theirs 提示执行同步。

只在 Core 增加文件但不登记 `COPY_MAP`，表示该文件仅供 Core 自身使用，不应出现在下游项目。

## 旧 Task 兼容

- schema 2/3 保持可读，不批量迁移。
- 旧 `active_iteration` 不再是默认加载授权。
- 只有 Task 仍在进行、准备重开、过长或频繁读取时才提出迁移。
- 迁移保持 Task ID、状态历史和证据，增加 Meta 与 Context Map。
- 需要移动旧原文时先给出迁移映射，经确认后完整归档并校验内容一致。

## 维护本仓库

修改规则、schema、Skill 或 CLI 时：

1. 使用本仓库 `.tasks/` 记录非轻量工作。
2. 保持根模板与 `.tasks/` 中本仓库自用模板一致。
3. 保持 `PROJECT_AGENTS.md`、`TASK_WORKFLOW.md`、Skill 和 CLI 行为一致。
4. 不加入私人路径、凭据、内部主机或单一业务项目事实。
5. 运行：

```bash
python3 -m unittest discover -s tests -v
python3 "${TRAE_HOME:-$HOME/.trae}/skills/.system/skill-creator/scripts/quick_validate.py" skills/task-runtime
.tasks/bin/taskctl doctor
git diff --check
```

6. 提交或推送前先展示范围并等待确认。

## 安全边界

- Task 文档中的命令仅作为文本保存，不会由 `taskctl` 自动执行。
- `context read` 只接受 Context Map 中声明的任务目录内文件。
- 初始化器不会覆盖不同内容，也不会修改 `.gitignore`。
- 代码、Git、测试和外部运行状态始终优先于 Task 中的历史描述。
