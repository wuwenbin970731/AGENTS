---
task_schema: 4
id: <YYYY-MM-DD-HHMMSS-slug>
title: <任务标题>
summary: "<用于任务匹配的稳定目标，一行>"
status: in_progress
mode: tracked
design_status: not_required
tags: []
checkpoint: "<当前进展，一行>"
next_action: "<恢复后的第一个动作，一行>"
revision: 1
created_at: <ISO-8601>
updated_at: <ISO-8601>
verified_at: null
parent_task: null
depends_on: []
---

# <任务标题>

## 任务契约

- 目标：<预期结果>
- 完成标准：<可验证结果>
- 范围：<文件、模块、数据或环境>
- 非目标：<明确不处理的事项>

## 当前工作状态

- 当前正在解决：<内容>
- 已确认的关键事实：<现场证据支持的内容>
- 当前方案或决定：<内容>
- 阻塞与解除条件：<无或内容>
- 下一次更新 Task 的触发点：<语义检查点>

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| `design/CURRENT.md` | <当前详细设计> | <只有何种工作需要读取> |

## 依赖契约

- 依赖任务：<无或 Task ID>
- 当前任务向其他任务提供：<无或输出契约>
- 当前任务从其他任务消费：<无或输入契约>
