---
task_schema: 5
task_id: <YYYY-MM-DD-HHMMSS-slug>
iteration: F000
status: in_progress
created_at: <ISO-8601>
updated_at: <ISO-8601>
completed_at: null
trigger: <initial / defect / regression / follow_up>
---

# <Fxxx：工作记录标题>

任务入口：[../TASK.md](../TASK.md)

> 本文件是按需读取的过程和证据，不是任务恢复时的默认上下文。

## 本轮边界

- 触发：<为何需要本轮记录>
- 目标：<可独立验收的结果>
- 范围：<文件、模块、数据或环境>
- 非目标：<内容>

## 事实与决策

- 初始状态或复现：<步骤与真实结果>
- 已确认事实：<path:symbol、测试或输出>
- 必须保持：<约束与验证方法>
- 本轮决定：<内容>
- 假设与未知项：<内容>

## 实际改动

| 文件与符号 | 改动 | 作用 |
|---|---|---|
| `<path:symbol>` | <内容> | <内容> |

## 执行与验证

| 时间 | 目录 | 命令或操作 | 结果 | 证据或产物 |
|---|---|---|---|---|
| <时间> | `<working-directory>` | `<command>` | pass / fail / blocked | `<path>` / 摘要 |

- 验证结论：<真实观察>
- 未覆盖边界：<无或内容>
- 大型证据：<../evidence/...、项目产物或不适用>

## 收束

- 写回 TASK 的当前结论：<内容>
- 最后完成：<里程碑>
- 尚未验证：<无或内容>
- 下一步：<动作或无>
- 完成时间：<null 或 ISO-8601>
