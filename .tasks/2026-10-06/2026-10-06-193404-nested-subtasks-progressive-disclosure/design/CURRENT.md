# 递归子 Task 与预算化渐进披露设计

## 1. 目标与不变量

- Task 形成任意深度的父子树，每个节点仍是可独立恢复、写入和验证的 Task。
- 路径表达物理归属，`parent_task` 表达权威父子关系，`subtask_key` 表达人可读层级地址。
- 打开一个节点不授权读取父、子、兄弟节点正文；其他节点默认保持 L0 Meta。
- 树遍历必须有深度和节点数量上限；资源读取必须先暴露成本并受显式预算约束。
- 旧 schema 2/3/4 Task 保持可发现；不批量迁移，不因升级运行时改写历史 Task。

## 2. Schema 5

新增 `subtask_key` Meta：

- 根 Task：`parent_task: null`、`subtask_key: null`。
- 直接子 Task：`S1`、`S2`。
- 更深层级：`S1.1`、`S1.2`、`S1.2.1`。
- Key 一经分配不重排；同一父 Task 下必须唯一。
- Key 只表示稳定工作单元，不隐含执行依赖；依赖继续由 `depends_on` 表达。

新 Task ID 保持时间戳前缀：

```text
<YYYY-MM-DD-HHMMSS>-<lowercase-subtask-key>-<slug>
```

根 Task 不含 key。`new --parent` 可显式传 `--subtask-key`；未传时在父 Task 短时锁内取直接子节点最大序号加一。

## 3. 存储布局

```text
.tasks/YYYY-MM-DD/<root-id>/
├── TASK.md
├── design/
└── subtasks/
    └── <child-id>/
        ├── TASK.md
        └── subtasks/<grandchild-id>/TASK.md
```

新 schema 5 子 Task 必须位于父 Task 的 `subtasks/` 下。schema 4 的扁平子 Task 继续通过 `parent_task` 构建虚拟树。

## 4. 渐进披露和树命令

- `children <task>`：只返回直接子节点 L0，默认最多 8 个。
- `tree <task>`：返回紧凑 L0 树，默认深度 1、最多 20 个节点；命令级深度有界但存储层级不设硬上限。
- `lineage <task>`：只返回祖先到当前节点的 L0 breadcrumb。
- `show --entry`：只把一个选中节点提升到 L1。
- `context list/read`：只处理当前节点资源，不能跨入 `subtasks/` 或任何后代 Task 边界。

树输出只保留 `id`、`subtask_key`、`title`、`status`、`summary`、`checkpoint`、`parent_task`、`child_count`、`tree_depth` 和 `path`。父 Task 不复制子 Task 正文或完整状态历史。

## 5. Token 与大小预算

- `context list` 动态返回每个合法资源的 `size_bytes` 和保守的 `estimated_tokens`，不读取正文。
- `context read` 默认限制为 32 KiB，可用 `--max-bytes` 或 `--max-tokens` 收紧或放宽。
- 超预算时命令拒绝读取并报告实际成本，不静默截断。
- Token 估算不是持久化事实；使用字节数作为确定性硬边界，按 `ceil(bytes / 3)` 给出保守估算。
- `TASK.md` 继续使用 frontmatter 1 KiB、入口 160 行建议值和 240 行硬上限。

## 6. 完整性与并发

`doctor` 新增以下检查：

- schema 5 父引用存在、父子无环。
- `subtask_key` 格式、父级前缀和兄弟唯一性正确。
- schema 5 子 Task 实际位于父目录的 `subtasks/<id>/TASK.md`。
- Context Map 不跨后代 Task 边界。
- Task 深度超过 5 层或路径过长时给出 warning。

自动分配 key 和创建子目录在父 Task 短时锁中完成，避免并发创建重复编号。Task 内容更新仍使用节点自身 ID 锁和 revision 检查。

## 7. 兼容与安装

- `.tasks/config.json` 和 `taskctl` 升级到 runtime 0.2.0、默认 schema 5。
- schema 4 继续完整校验和读写；schema 2/3 继续只读兼容。
- 新增 `schema-v5.md` 并由初始化器安装；保留 `schema-v4.md` 供旧 Task 迁移时按需读取。
- 根模板与 `.tasks/` 自用副本保持字节一致。
- 下游更新仍走 base/ours/theirs 语义合并，不由初始化器覆盖已有项目。

## 8. 验收

- 创建根 Task、`S1`、`S2`、`S1.1`，路径、Meta 和 ID 均符合协议。
- tree/children/lineage 只返回 L0 且遵守深度和数量上限。
- 父 Context Map 无法读取子 Task 文件；超预算资源无法读取。
- doctor 能发现缺父、重复 key、key 前缀错误、环和路径不一致。
- 初始化器、完整单测、Skill 校验、doctor 和 `git diff --check` 全部通过。
