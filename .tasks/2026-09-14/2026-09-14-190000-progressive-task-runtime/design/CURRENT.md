# Task 渐进式披露设计

## 1. 设计目标

- Task 可跨多个会话持续推进，但不依赖聊天历史恢复。
- Agent 可以发现其他 Task，但搜索结果只包含 Meta。
- 选择 Task 后只加载 `TASK.md`，随后根据 Context Map 显式读取单个资源。
- 当前状态、详细设计、过程证据和归档按职责分离。
- 多会话写入使用 revision 和短时文件锁，不能最后写入者静默覆盖。
- 核心仓库能够安全初始化新项目，同时保留目标项目已有内容。

## 2. 加载状态机

```text
light 请求 ────────────────────────────────────────▶ 不进入 Task 流程

tracked / rigorous / resume
    │
    ├─ 显式 ID 或路径 ────────────────┐
    ├─ 有效 session binding ──────────┤
    └─ Meta 搜索，最多八个候选 ───────┤
                                      ▼
                              选中一个 Task（L0）
                                      │
                                      ▼
                                读取 TASK.md（L1）
                                      │
                         当前意图满足 read_when？
                              │               │
                              否              是
                              │               ▼
                              │       显式读取一个资源（L2/L3）
                              └───────────────┘
```

链接本身不是读取授权；关联 Task 默认仍停留在 L0；资源中的链接不递归展开。

## 3. 数据边界

- `.tasks/YYYY-MM-DD/<task-id>/TASK.md`：任务契约和当前权威状态。
- `design/`：当前详细设计。
- `runbooks/`：可复用运行和恢复步骤。
- `decisions/`：需要长期解释原因的决定。
- `iterations/`：按需读取的单轮过程证据。
- `evidence/`：大型证据。
- `archive/`：旧原文。
- `<git-dir>/task-state/`：session binding 和短时锁；不可写时降级到已忽略的 `.tasks/.state/`。

## 4. CLI 契约

- `search`、默认 `show` 和 `related` 只输出 Meta。
- `show --entry` 输出一份 `TASK.md`，不展开链接。
- `context list` 只输出资源清单；`context read` 只读取 Context Map 声明的单文件。
- `new` 默认只创建 `TASK.md`。
- `update` 更新 Meta 检查点；`write` 更新完整入口。二者都要求预期 revision。
- `bind/current/unbind` 维护本地会话关联。
- `doctor` 检查 schema、重复 ID、预算、资源边界和链接存在性。

## 5. 写入与并发

```text
读取 revision=N
  → 完成当前工作和资源写入
  → 获取短时锁
  → 再读 revision
  → 相同：原子写入 revision=N+1
  → 不同：退出码 3，重新读取并语义合并
```

锁只覆盖最后一次写入，五分钟后可视为陈旧；会话绑定不是写锁。

## 6. 初始化策略

- `scripts/init_project.py <project>` 默认只展示计划。
- 显式 `--apply` 才创建缺失文件。
- 目标 `.tasks/` 非空但没有本仓库 marker 时停止。
- 任何目标文件内容不同时停止，交由三方语义合并，不自动覆盖。
- 初始化安装项目 `AGENTS.md`、`.tasks` 运行时和项目本地 `task-runtime` Skill。

## 7. 兼容策略

schema 2/3 可搜索和读取，旧 `active_iteration` 不再自动加载。只在重新激活时增量补充 Meta 和 Context Map，保持 Task ID、历史和证据不变。
