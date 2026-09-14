# Task Workflow

本文件定义 `.tasks/` 中持久化任务的创建、加载、写入和迁移协议。普通任务恢复由 `.tasks/bin/taskctl` 和 `task-runtime` Skill 执行，不应默认把本文件加载进上下文。

## 1. 记录级别

| 级别 | 场景 | 记录方式 |
|---|---|---|
| `light` | 局部、低风险、单会话可完成 | 不搜索或创建 Task |
| `tracked` | 多步骤、可能中断、需要跨会话恢复 | 创建精简 `TASK.md` |
| `rigorous` | 架构、公共接口、数据迁移、远程长任务、难回滚副作用或重要验收不确定性 | `TASK.md` 加按需详细设计 |

工作升级时可以创建或提升 Task；不要仅因修改多个文件选择 `rigorous`。

## 2. 存储布局

```text
.tasks/
├── config.json
├── bin/taskctl
├── TASK_WORKFLOW.md
├── TASK_TEMPLATE.md
├── TASK_ITERATION_TEMPLATE.md
└── YYYY-MM-DD/<task-id>/
    ├── TASK.md
    ├── design/
    ├── runbooks/
    ├── decisions/
    ├── iterations/
    ├── evidence/
    └── archive/
```

- 每个新 Task 只要求 `TASK.md`，其他目录按需创建。
- Task 内容可以进入 Git；会话绑定和锁优先位于 Git 私有目录 `task-state/`，不可写时降级到已忽略的 `.tasks/.state/`。
- `TASK.md` frontmatter 是 Meta 的唯一权威来源；索引只能是可重建缓存。
- 若项目已经有其他用途的 `.tasks/` 且没有本仓库的 `config.json` 标记，不得接管。

## 3. 四级渐进披露

| 层级 | 内容 | 加载条件 |
|---|---|---|
| L0 | Task Meta | 搜索或查看关联任务 |
| L1 | 当前任务 `TASK.md` | 确定当前任务后 |
| L2 | 当前设计、runbook、decision | Context Map 的读取条件匹配当前工作 |
| L3 | iteration、evidence、archive | 需要追溯或核验具体结论 |

进入某层不代表递归读取下一层。其他任务默认停留在 L0；只有它的准确契约影响当前决策或用户要求切换时才读取其入口。

## 4. 发现、选择与创建

1. 用户明确提供 Task ID 或路径时，直接 `taskctl show <task> --entry`。
2. 有稳定会话 ID 时，先执行 `taskctl current --session <id>`；目标仍一致才恢复绑定。
3. 否则执行 `taskctl search "<目标关键词>" --limit 8`，只获取 Meta。
4. 唯一高置信候选可以打开入口；多个候选需让用户选择。
5. 没有相同目标或完成边界的任务时，使用 `taskctl new` 创建。
6. 确定任务后，有稳定会话 ID时使用 `taskctl bind`。

搜索不得通过读取所有 `TASK.md` 正文实现。`taskctl` 只解析 frontmatter，并且默认不返回已完成任务。

## 5. `TASK.md` 职责

`TASK.md` 只保存：

- 供搜索和恢复使用的 Meta。
- 目标、完成标准、范围与非目标。
- 当前关键事实、决定、阻塞和检查点。
- 按需资源的内容摘要与确定性读取条件。
- 任务之间的输入输出依赖契约。

完整历史、聊天转录、原始日志、大错误栈和详细实现证据不得堆入入口。frontmatter 建议不超过 1 KiB；入口建议不超过 160 行，超过 240 行视为结构错误。

## 6. 按需资源

- 当前详细设计过大时写入 `design/CURRENT.md`。
- 可复用启动、恢复、停止或迁移步骤写入 `runbooks/`。
- 需要长期解释原因的关键决策写入 `decisions/`。
- 单轮实现、实验或排障过程写入 `iterations/`。
- 大型日志和产物写入 `evidence/` 或项目正式产物目录。
- 旧式任务原文迁入 `archive/`。

每个可加载资源都必须列入 Context Map，并写明读取条件。加载器只允许显式读取已声明的任务内文件，拒绝绝对路径、`..`、目录、glob 和符号链接逃逸。

## 7. 检查点与并发写入

只在语义状态发生变化时写 Task：目标或范围改变、形成决定、设计就绪、已验证里程碑、阻塞、长任务状态变化、中断、完成或重开。普通编辑和探索命令不触发入口更新。

写入顺序：

1. 先更新详细资源或证据。
2. 使用最初读到的 `revision` 作为 `--expect-revision`。
3. `taskctl` 在短时锁内重新检查 revision，并使用同目录临时文件原子替换。
4. revision 一致则递增后写入；不一致则退出，不得覆盖，重新读取并语义合并。

锁只覆盖最终写入，不能持有整个会话。一个 Task 可以被多个会话绑定，绑定不表示写入所有权。

## 8. 设计、验证和完成

`design_status` 使用 `not_required`、`draft`、`awaiting_user`、`implementation_ready`、`implemented`。`rigorous` 任务在 `implementation_ready` 且无阻塞决策后开始正式编码。

任务记录不是现场状态的替代品。恢复和完成前重新检查 Git、代码、测试、日志、输出和外部进程。完成时必须满足完成标准，关闭阻塞，记录真实验证边界，并将下一步设置为无或明确的后续任务。

## 9. 旧任务兼容和迁移

- schema 2/3 继续可读，不批量升级。
- 旧 `active_iteration` 只作为兼容字段，普通恢复不自动加载。
- 只有旧任务仍活动、重开、过长或频繁读取时才提出迁移。
- 迁移保持 Task ID、完成历史和原始证据；增加 schema 4 Meta 和 Context Map，不为格式统一重写历史。
- 旧单文件原文需要移动时，先提交只读映射供用户确认，再完整归档并校验内容一致。

## 10. 安全与检查

- Task 中的命令只是文本，加载后不得自动执行。
- 不记录凭据、令牌、私人地址、内部主机或其他敏感数据。
- 不自动将 `.tasks/` 加入 `.gitignore`。
- 结构修改后运行 `.tasks/bin/taskctl doctor`。
- 未经用户确认提交范围，不自动暂存、提交或推送 Task 内容。
