---
task_schema: 3
id: <YYYYMMDD-HHMMSS-slug>
mode: tracked
status: in_progress
design_status: draft
active_iteration: iterations/F000-initial.md
created_at: <ISO-8601>
updated_at: <ISO-8601>
parent_task: null
relationship: null
legacy_document: null
---

# <任务标题>

## 当前快照

- 目标：<预期结果>
- 当前状态：<已完成、正在做或阻塞原因>
- 当前迭代：[F000](iterations/F000-initial.md)
- 下一步：<一个具体动作>
- 主要风险：<无或内容>

## 完成标准与范围

- [ ] <功能或交付结果>
- [ ] <必须保持的边界>
- [ ] <验证和可解释性结果>

- 范围内：<内容>
- 非目标：<内容>

## 当前事实与设计

| 当前事实或约束 | 证据 | 影响 |
|---|---|---|
| <内容> | `<path:symbol>` / test / output | <影响> |

```text
<入口 path:symbol> → <关键处理> → <外部边界> → <输出>
```

- 核心模块职责：<文件与符号及其职责>
- 当前接口或参数：<仅保留调用、复现或兼容所需内容>
- 关键不变量与异常：<内容>
- 详细设计：<活动迭代、design/CURRENT.md、项目文档或“不适用”>

| 决策或假设 | 类型 | 状态 | 影响 |
|---|---|---|---|
| <内容> | blocking / non_blocking | awaiting_user / confirmed / assumed | <影响> |

## 状态、迭代与关联任务

| 时间 | 状态变化 | 原因 | 迭代 |
|---|---|---|---|
| <时间> | `pending → in_progress` | <原因> | F000 |

| 迭代 | 状态 | 摘要 | 文档 | 完成时间 |
|---|---|---|---|---|
| F000 | in_progress | <摘要> | [iterations/F000-initial.md](iterations/F000-initial.md) | - |

| 关联任务 | 关系 | 原因 |
|---|---|---|
| 无 | - | - |

## 当前可复用命令

### <用途或“不适用”>

- 目录：`<working-directory>`
- 前置条件与参数：<内容>
- 预期结果：<产物或成功信号>

```bash
<command>
```

## 当前验证与排障

| 层级 | 结论 | 最近证据 | 未覆盖边界 |
|---|---|---|---|
| local / integration / e2e / data | pass / fail / blocked | [F000](iterations/F000-initial.md) / `<path>` | <内容> |

| 故障表现 | 第一检查点 | 最小复现或检查 |
|---|---|---|
| <现象> | `<path:symbol>` / log / state | `<command or steps>` |

## 恢复入口

- 最后完成：<里程碑与验证>
- 当前进行：<内容>
- 修改文件：<列表>
- 尚未验证：<无或内容>
- 阻塞与解除条件：<无或内容>
- 下一步：<一个具体动作>
- 恢复时重新检查：Git、代码、测试、日志、输出和外部进程。
