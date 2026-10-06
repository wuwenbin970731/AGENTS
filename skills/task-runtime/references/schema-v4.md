# Task Schema 4 (Compatibility)

Schema 4 remains writable in place for existing flat tasks. New tasks use schema 5; migrate only an active task that needs recursive identity or nested storage.

## Contents

1. Required metadata
2. Entry body
3. Context Map
4. Limits and validation

## 1. Required metadata

```yaml
---
task_schema: 4
id: 2026-09-14-190000-progressive-task-disclosure
title: Task 渐进式披露
summary: "建立跨会话恢复、Meta 搜索和按需加载能力"
status: in_progress
mode: rigorous
design_status: draft
tags: [agents, task-system, context]
checkpoint: "正在评审 schema 4 和加载协议"
next_action: "完成 taskctl 第一版"
revision: 7
created_at: 2026-09-14T19:00:00+08:00
updated_at: 2026-09-14T20:00:00+08:00
verified_at: null
parent_task: null
depends_on: []
---
```

Statuses are `pending`, `in_progress`, `awaiting_user`, `blocked`, and `completed`. Modes are `tracked` and `rigorous`. Design statuses are `not_required`, `draft`, `awaiting_user`, `implementation_ready`, and `implemented`.

Keep `summary` stable. Replace `checkpoint` and `next_action` as current state changes. Increment `revision` on every managed entry write.

## 2. Entry body

Use exactly the sections needed from this stable shape:

- `任务契约`: goal, completion criteria, scope, and non-goals.
- `当前工作状态`: current problem, facts, decisions, blocks, and next checkpoint condition.
- `按需上下文地图`: resources and deterministic read conditions.
- `依赖契约`: explicit dependencies and provided or consumed outputs.

Do not keep complete status history, chat transcripts, raw logs, or full iteration bodies in the entry.

## 3. Context Map

Use a Markdown table with exactly these first three columns:

```markdown
| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| `design/CURRENT.md` | 当前完整设计 | 修改接口或实现时 |
```

Paths are relative to the task directory. Declare only files, not directories or globs. A loader must reject undeclared paths, missing files, absolute paths, `..` escapes, and symlink escapes.

## 4. Limits and validation

- Frontmatter target: at most 1 KiB.
- `TASK.md` target: at most 160 lines; more than 240 lines is invalid.
- Search output: at most eight candidates by default.
- Resources are never recursively expanded.
- Run `taskctl doctor` after structural edits.
