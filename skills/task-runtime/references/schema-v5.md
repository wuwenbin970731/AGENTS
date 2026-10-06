# Task Schema 5

## Contents

1. Required metadata
2. Recursive task identity
3. Entry body and Context Map
4. Limits and compatibility

## 1. Required metadata

```yaml
---
task_schema: 5
id: 2026-10-06-143000-s1-data-preparation
title: 数据准备
summary: "准备并验证训练输入"
status: in_progress
mode: rigorous
design_status: implementation_ready
tags: [data, training]
checkpoint: "数据契约已确认"
next_action: "实现数据验证"
revision: 3
created_at: 2026-10-06T14:30:00+08:00
updated_at: 2026-10-06T15:00:00+08:00
verified_at: null
parent_task: 2026-10-06-140000-model-training
subtask_key: S1
depends_on: []
---
```

Statuses are `pending`, `in_progress`, `awaiting_user`, `blocked`, and `completed`. Modes are `tracked` and `rigorous`. Design statuses are `not_required`, `draft`, `awaiting_user`, `implementation_ready`, and `implemented`.

Keep `summary` stable. Replace `checkpoint` and `next_action` as current state changes. Increment `revision` on every managed entry write.

## 2. Recursive task identity

- A root task has `parent_task: null` and `subtask_key: null`.
- A direct child uses `S1`, `S2`, and so on.
- A deeper child extends its parent's key by one numeric segment: `S1.1`, `S1.2`, `S1.2.1`.
- `parent_task` and the key are immutable in normal writes and unique among siblings. Reparenting requires an explicit structural migration.
- Dependencies remain explicit in `depends_on`.

Root tasks live at `.tasks/YYYY-MM-DD/<task-id>/TASK.md`. A child lives at `<parent-task-dir>/subtasks/<task-id>/TASK.md`. Opening one node never authorizes opening another node's entry or resources.

## 3. Entry body and Context Map

Use exactly the sections needed from this stable shape:

- `任务契约`: goal, completion criteria, scope, and non-goals.
- `当前工作状态`: current problem, facts, decisions, blocks, and next checkpoint condition.
- `按需上下文地图`: resources and deterministic read conditions.
- `依赖契约`: explicit dependencies and provided or consumed outputs.

Context Map paths are relative to the current task directory. Declare only files, not directories or globs. A loader must reject undeclared paths, missing files, absolute paths, `..` escapes, symlink escapes, `subtasks/`, and any path governed by a descendant `TASK.md`.

## 4. Limits and compatibility

- Frontmatter target: at most 1 KiB.
- `TASK.md` target: at most 160 lines; more than 240 lines is invalid.
- Search output: at most eight candidates by default.
- Tree output: bounded by explicit depth and item limits; no command performs unlimited recursive disclosure.
- Resource listings expose byte size and an estimated token cost before reading.
- Resource reads fail when they exceed the caller's budget; content is never silently truncated.
- Schema 4 remains writable in place. Schema 2/3 remain readable and require explicit migration before managed writes.
- Run `taskctl doctor` after structural edits.
