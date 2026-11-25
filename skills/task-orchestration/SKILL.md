---
name: task-orchestration
description: Plan and coordinate persistent Subtasks through Orca terminal or chat agents, with sequential acceptance gates, parallel batches, and durable execution bindings. Use when preparing, executing, or resuming Subtasks in Orca; creating Subtasks alone does not authorize launching workers.
---

# Task Orchestration

Use this skill with `task-runtime` for persistent tasks and Orca's `orchestration` and `orca-cli` skills for live execution. It is a coordinator protocol, not a background scheduler. If a required skill or CLI is unavailable, retain the plan and report the missing capability; do not substitute in-process subagents.

## Prepare an execution plan

1. Resolve the parent through `task-runtime`. Discover bounded metadata only. Default to direct children; when the user requests descendants or an entire task tree, traverse the explicitly selected scope through bounded Meta queries. Do not recursively load entries or resources. For descendant execution read [references/descendants.md](references/descendants.md) and use `scripts/planctl.py` for validation, Chinese Review rendering and scheduling-frontier calculation.
2. Read [references/execution.md](references/execution.md) before creating a plan, dispatching work, accepting results, or recovering a run. It defines the plan record, transitions, and worker brief.
3. Resolve project defaults from an explicit project `AGENTS.md` preferences section, then apply the user's current overrides. Modes are `manual-sequential` (default), `auto-sequential`, and `parallel`. At each selected parent, parallel selects all included children; an explicit selection limits the batch. Hierarchical plans attach an inherited/overridden policy to each parent, with coordinator aggregates and executable leaves. Freeze IDs and order for this plan; later children are not implicitly included.
4. Use a configured or user-selected Agent; if none is known, ask once before launch. Do not invent a model or effort. Read [references/surfaces.md](references/surfaces.md) to resolve `terminal` / `chat`: per-item selection overrides the batch selection, otherwise follow the verified current caller surface. Resolve and freeze new schema 3 leaves before Review; unknown caller identity is not implicitly terminal. Default `display_title` is `<parent short name> · <subtask key> · <short title>`, adding an attempt suffix on retries. Codex `session_name` defaults to that title but remains a separate provider name. Existing schema 2 plans retain terminal semantics and original digests.
5. Before first launch, present a visual execution tree for user Review as specified in [references/visual-review.md](references/visual-review.md). Show the resolved scope, per-parent scheduling, execution/coordinator roles, acceptance gates, dependencies, Agent and terminal names. Persist the reviewed snapshot and its plan version. An execution request expresses intent; launch only after the concrete tree is approved. If the user already approved that exact tree and requested execution, do not ask again. Planning or creating Subtasks alone does not authorize execution.

## Execute and supervise

- Persist the plan under the parent and declare its exact path in the parent's Context Map. Record an attempt before external launch and save returned bindings immediately. Reconcile other declared active plans before launching the same Subtask again.
- Load the version-matched Orca guides. Use supervised workers, not a full handoff: the main Agent retains coordination and receives results. Use the existing workspace by default. Sharing conflicting edits is a blocker; resolve scheduling or workspace placement without silently creating worktrees.
- Preserve the reviewed surface, title, and availability for user inspection. Follow surfaces.md for explicit launch then supervised binding when high-level worker-start cannot select a surface. Verify actual outcome before dispatching the brief; a fallback to a different surface does not satisfy the plan. Use dispatch-based supervision for both kinds, not terminal input.
- For Codex workers, read [references/session-naming.md](references/session-naming.md). Generate a unique marker per attempt and include a non-blocking identity initialization in the worker brief when native binding is unavailable. Prefer exact native provider-thread binding, then structured worker initialization, then an already-enabled fresh unique index lookup. After verifying the binding, the coordinator uses `scripts/sessionctl.py` to set and read back the chat name. Do not send `/status`, `/rename`, extra prompt text or resume commands to a running worker. Naming pending/conflict never blocks task scheduling or acceptance.
- Apply scheduling locally at each parent: `manual-sequential` enters one child branch and waits for user acceptance of that child’s overall result before entering its next sibling. `auto-sequential` advances after evidence checks; `parallel` enters eligible included branches. A branch may use a different policy internally. Aggregate parents do not get execution instances; run aggregate checks after selected children are accepted, then honor the upstream acceptance gate. Use schema 2/3 `ready` output before every descendant launch or progression; it never replaces live Orca checks or recorded human acceptance.
- Follow Orca's receipt `next` and wake mechanism. Do not add polling/watch scripts. End the turn when waiting for a worker or user acceptance; this does not complete the persistent Task.
- A terminal receipt, accepted prompt, worker report, or idle terminal is not proof that a Subtask meets its completion criteria. Keep execution outcome, acceptance, and Task metadata separate.
- On ambiguous launch, failure, interruption, or resumed coordination, inspect live Orca state and load its applicable recovery reference. Do not relaunch on silence or blindly repeat a create command.

## Persist and report

面向用户的方案、结果、可视化、图例、状态和验收提示尽可能使用中文。模式展示为“验收串行 / 自动串行 / 并行”，节点角色展示为“协调汇总 / 执行”。Task ID、层级编号、命令、路径、程序字段与返回标识保留原值；中文展示不改变底层枚举和接口。terminal 名称中的可读标题优先使用中文。

The coordinator owns plan writes and acceptance; workers own their assigned Task and allowed edits. Use `taskctl write/update --expect-revision` for Task entries. At a checkpoint report each affected Subtask's execution state, acceptance state, actual surface and instance binding, evidence, and next action. Preserve attempt history; do not close execution instances or remove workspaces unless requested.
