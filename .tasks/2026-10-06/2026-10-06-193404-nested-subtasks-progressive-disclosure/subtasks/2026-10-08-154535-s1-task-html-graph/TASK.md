---
task_schema: 5
id: "2026-10-08-154535-s1-task-html-graph"
title: "Task HTML 关系图谱"
summary: "从有界 L0 Task 元数据生成可重复刷新的单文件 HTML 关系图谱，并展示层级与完成状态"
status: "completed"
mode: rigorous
design_status: "implemented"
tags: ["task-system", "visualization", "html"]
checkpoint: "taskctl graph 已实现；28 项单测与真实 answer-me-with-html 渲染通过"
next_action: "无；按需运行 taskctl graph 刷新父 Task 的关系和状态快照"
revision: 3
created_at: 2026-10-08T15:45:35+08:00
updated_at: "2026-10-08T15:56:52+08:00"
verified_at: "2026-10-08T15:56:52+08:00"
parent_task: "2026-10-06-193404-nested-subtasks-progressive-disclosure"
subtask_key: "S1"
depends_on: []
---

# Task HTML 关系图谱

## 任务契约

- 目标：从有界 L0 Task 元数据生成可重复刷新的单文件 HTML 关系图谱，并展示层级与完成状态
- 完成标准：`taskctl graph` 能从有界 L0 Meta 生成单文件 HTML；状态、层级、预算和剩余节点信息准确；失败保持原文件；初始化、文档和自动化测试通过。
- 范围：`taskctl` 图谱命令、可选 answer-me-with-html 发现和调用、文档、版本、初始化结果与测试。
- 非目标：浏览器内编辑 Task、后台常驻刷新、把 HTML 作为事实源、自动读取 Task 正文或后代资源。

## 当前工作状态

- 当前正在解决：实现并验证 `taskctl graph` 的可重复 HTML 渲染流程。
- 已确认的关键事实：现有 `tree` 已提供有界 L0 数据；answer-me-with-html 支持从标准输入渲染到指定单文件；当前父链含一个 `awaiting_user` 根节点和一个 `completed` 子节点。
- 当前方案或决定：Task Meta 保持唯一事实源；图谱是显式刷新的派生快照；使用临时文件和原子替换；缺少渲染器不影响现有查询能力。
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：CLI、文档和测试实现完成并通过验证。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| `design/CURRENT.md` | CLI 契约、数据边界、渲染流程、失败语义和验收标准 | 修改图谱接口、渲染实现或验收范围时 |

## 依赖契约

- 依赖任务：父 Task `2026-10-06-193404-nested-subtasks-progressive-disclosure` 提供递归树与 L0 查询能力。
- 当前任务向其他任务提供：可移植的 Task HTML 图谱生成命令和静态证据页。
- 当前任务从其他任务消费：`tree` 的有界遍历、Schema 4/5 兼容和 answer-me-with-html 渲染 CLI。
