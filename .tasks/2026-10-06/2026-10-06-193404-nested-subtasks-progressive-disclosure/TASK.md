---
task_schema: 4
id: "2026-10-06-193404-nested-subtasks-progressive-disclosure"
title: "递归子 Task 与预算化渐进披露"
summary: "让 Task 支持带层级编号的递归子任务，并在树遍历和资源加载时实施渐进披露与 Token 预算边界"
status: "completed"
mode: rigorous
design_status: "implemented"
tags: ["task-system", "taskctl", "progressive-disclosure"]
checkpoint: "Task Runtime 0.2.0 已实现并通过完整验证，HTML 改动说明已存入 Task evidence"
next_action: "无；按 README 的 base/ours/theirs 流程同步下游仓库"
revision: 8
created_at: 2026-10-06T19:34:04+08:00
updated_at: "2026-10-08T18:09:47+08:00"
verified_at: "2026-10-06T19:45:25+08:00"
parent_task: "2026-09-14-190000-progressive-task-runtime"
depends_on: []
---

# 递归子 Task 与预算化渐进披露

## 任务契约

- 目标：让 Task 支持带层级编号的递归子任务，并在树遍历和资源加载时实施渐进披露与 Token 预算边界
- 完成标准：Schema 5 可创建 S1/S2/S1.1 嵌套 Task；树查询保持 L0 且有预算；Context Map 不能越过子 Task 边界；旧 schema 4 保持可用；文档、模板、初始化器和完整验证一致通过。
- 范围：`taskctl`、schema/protocol/Skill、Task 模板与工作流、项目初始化映射、项目规则、README 和自动化测试。
- 非目标：批量迁移现有下游 Task；自动同步下游仓库；自动提交或推送。

## 当前工作状态

- 当前正在解决：实现、文档同步和验证均已完成。
- 已确认的关键事实：runtime 0.2.0 已支持 schema 5、`S1/S1.1` 递归编号和嵌套目录；`children/tree/lineage` 保持有界 L0；Context Map 资源不能跨后代 Task，读取前报告成本并执行预算。
- 当前方案或决定：新 Task 使用 schema 5；旧 schema 4 原地可读写并参与虚拟树；schema 2/3 保持只读兼容；下游通过现有 base/ours/theirs 流程增量同步，不批量迁移 Task。
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：下游同步发现兼容问题，或需要提供显式 reparent/migration 命令时重开。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| `design/CURRENT.md` | Schema 5、递归布局、树查询、Token 预算和兼容策略 | 修改协议、CLI、模板或检查实现是否符合设计时 |
| `evidence/task-runtime-0.2.0-explainer.html` | 主要改动、核心代码和验证结果的可视化说明 | 向用户或下游维护者讲解本次升级时 |
| `design/task-graph-visualization-proposal.html` | Task 关系图谱的派生视图架构、刷新策略和渐进披露边界 | 评审或实现 Task 图谱可视化时 |
| `evidence/task-graph.html` | 当前父 Task 与后代状态的有界 L0 HTML 图谱 | 人工查看父子关系、完成状态或选择下一节点时 |

## 依赖契约

- 依赖任务：`2026-09-14-190000-progressive-task-runtime`（现有 Task Runtime 基线）。
- 当前任务向其他任务提供：可同步到下游的递归 Task Runtime 0.2.0、协议和迁移边界。
- 当前任务从其他任务消费：schema 4 渐进披露、revision 写入和初始化 Review gate。
