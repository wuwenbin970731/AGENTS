# Execution plans and coordination

## Contents

1. Defaults and authorization
2. Plan record and write ownership
3. Selection and dependencies
4. Launch and worker brief
5. Completion and acceptance
6. Recovery

## 1. Defaults and authorization

Optional project preferences belong outside managed global blocks in project `AGENTS.md`:

```yaml
# Example preferences, not implicit authorization to launch
subtask_execution:
  backend: orca
  mode: manual-sequential
  agent: null
  surface: terminal
  title_template: "{parent_short} · {subtask_key} · {title}"
```

This is a documented preference section, not an automatically parsed configuration file. Explicit per-item choices override this plan's defaults; current user instructions override stored preferences. Agent is the application/CLI choice, e.g. codex or claude, separate from model and effort. Null Agent requires a choice before launch. Use a user/configuration-selected model or effort only when supplied. An agreed project default counts as a selection; do not infer it from the coordinator's own model.

A request such as “按默认方式执行这些 Subtask” expresses execution intent. First present the concrete visual execution tree under [visual-review.md](visual-review.md), then obtain user approval of that plan before launch. If the user already approved the same tree and requested execution, do not ask again. “创建三个 Subtask” only creates tasks; surface the execution option without starting agents. Do not request launch confirmation repeatedly within the reviewed and authorized plan. Plan Review is separate from later per-Subtask acceptance, which remains mandatory in manual mode. Do not start real workers while merely designing this workflow.

## 2. Plan record and write ownership

The schema 1 example below remains the legacy flat/direct-child protocol. For descendant execution use schema 2 from [descendants.md](descendants.md), its node-level scheduling and `planctl.py`; do not flatten a multi-level strategy into `items`. Existing schema 1 records remain readable, but must be explicitly migrated and reviewed before using the schema 2 helper. Preserve old attempts and acceptance records; never auto-launch during migration.

Save each plan at `orchestration/<plan-id>.json` inside the selected parent Task directory. Generate an ID with a timestamp and random suffix, not a title. Register that exact resource in the parent's Context Map with a condition such as “executing or recovering this batch”. Prefer a single bounded plan record; split old attempt evidence into declared resources if size grows past the context budget. Load with `context list/read` before editing an existing plan.

The following illustrates the required information; runtime identifiers are null until returned by Orca. Names are labels, never identity keys.

```json
{
  "schema": 1,
  "plan_id": "<timestamp-random>",
  "revision": 1,
  "plan_version": 1,
  "review": {"status": "pending", "plan_version": 1, "artifact": "orchestration/<plan-id>-v1.md", "basis": null},
  "parent_task": "<stable Task ID>",
  "authorization": {"state": "planned", "basis": null},
  "mode": "manual-sequential",
  "defaults": {"agent": "codex", "surface": "terminal"},
  "items": [
    {
      "task_id": "<stable child ID>",
      "subtask_key": "S1",
      "task_revision_at_plan": 1,
      "depends_on": [],
      "agent": "codex",
      "model": null,
      "effort": null,
      "terminal_title": "Example · S1 · Implement feature",
      "completion_criteria": ["<observable result and required evidence>"],
      "attempts": []
    }
  ]
}
```

Keep `plan_version` for scheduling/content changes distinct from `revision` for every record write. Review references the exact strategy version and snapshot; a new attempt status alone does not invalidate Review. Store the Review artifact as an explicit Context Map resource, derived from the same plan. See [visual-review.md](visual-review.md) for review invalidation and hierarchical plan scope.

Array order is execution order. Store authorization as `planned` or `authorized`, with a short basis referencing the user's instruction; do not store chat transcripts. Each attempt has:

- `attempt_id`, `state`, `created_at`, `updated_at`;
- `binding`: backend, workspace selector, terminal handle, Agent session/handle when available, Orca run/task/dispatch IDs and launch operation/request IDs when available;
- `result`: outcome (`succeeded`/`failed`), evidence references, blockers, or null;
- `acceptance`: status (`pending`/`accepted`/`rejected`), actor (`user`/`coordinator`), basis, timestamp;
- `recovery`: observations and superseded-attempt reference when relevant.

Runtime handles/host selectors may be private. Keep private routing data in project-local ignored state when required by project policy; store an opaque binding reference in the versionable plan. Never put credentials, private addresses, internal hosts, raw command environments, or secret-bearing receipts in Task files. Persist only the minimum sanitized fields; retain actual receipt details in suitable local state if needed.

One coordinator writes a plan. Read the current revision, use a short exclusive plan lock, compare revision, increment, and replace via a same-directory temporary file. On conflict reopen and merge; do not hold locks while waiting for workers or users. This is an Agent-maintained protocol, not an enforced taskctl schema or lock implementation. Do not present it as a machine-enforced scheduler. Concurrent coordinators must agree one owner before mutation; otherwise stop writes and reconcile.

Update the resource before its Task checkpoint. If interrupted between them, reconcile the orphan resource before creating another plan. Task metadata remains authoritative for Task status; the plan is authoritative for the batch's selection, acceptance gate, and recorded execution attempts, subject to live runtime verification.

## 3. Selection and dependencies

Schema 2 permits descendants with the ancestor chain and per-parent policies described in [descendants.md](descendants.md). Recursive scheduling never authorizes recursive context loading. The following dependency, ownership and live-recheck requirements also apply to hierarchical plans.

- For schema 1, `all` means all direct children discovered through bounded metadata queries, frozen as stable IDs. Confirm queries are not truncated before claiming a complete selection. If the CLI's bound cannot represent the whole set, report this limit and form explicit bounded batches; never treat a truncated list as all.
- For schema 1, an explicit subset must consist of direct children of the selected parent, with no duplicate IDs. Do not silently expand descendants or add dependencies outside the selection.
- Natural ordering uses numeric hierarchy segments (`S2` precedes `S10`); user order wins. Reject a serial order that contradicts dependencies instead of silently reordering it.
- Resolve `depends_on` to stable task identities. Unknown dependencies, cycles, unmet dependencies outside the batch, and ambiguous references block the affected launch; report exactly which task is needed.
- Before launch recheck child metadata and dependencies. Scope/criteria changes invalidate the affected brief and require reconciliation with the authorized goal; ordinary revision changes alone do not require repeated user approval.
- A selected dependency must pass this plan's acceptance gate before it releases a dependent task, even if a worker prematurely marked it completed. External dependencies require authoritative completed Task status plus their stated output contract.
- Do not rerun completed tasks by default. Preserve them in the selection with a recorded skip reason. Reopening requires user intent. A skipped completed dependency does not require a new acceptance unless its output is being challenged.
- Before concurrent launch compare allowed edit scopes. If they conflict, serialize the affected tasks or resolve workspace placement with the user. Parallel mode does not authorize worktree creation or automatic merging.

## 4. Launch and worker brief

Read Orca's installed `orchestration` guide and relevant conditional references. Keep Orca task/run IDs distinct from persistent Task IDs. Use a supervised worker: results and questions must return to the coordinator. Prefer Orca's own dependency and message machinery where compatible, but keep human acceptance as a coordinator-side release gate. Do not queue a dispatch in a way that allows it to start before that gate.

For each eligible task:

1. Persist a `prepared` attempt with stable attempt ID. Verify no active attempt for this Task is recorded in another declared plan; inspect live runtime when recovering. Without exclusive ownership, do not launch.
2. Select the existing workspace, terminal title, Agent and brief. Verify current CLI support for terminal surface, naming and keeping terminals open. Load `references/low-level-topology.md` when composing a terminal and worker binding rather than using the high-level launch. Resolve custom Agent commands through Orca's configuration/guide; never invent executable arguments from an Agent name.
3. Save `launching` immediately before the external operation. Record each successfully created resource before the next external step (e.g. terminal creation before dispatch). Follow the version-matched receipt and store operation IDs. Do not paste the same prompt again to prove delivery.
4. Save exact returned bindings. Set `running` only when launch/dispatch is confirmed by Orca; if evidence proves only input acceptance, record that limit and continue the documented observation path. Title and terminal surface must match the plan; a chat is a mismatch, not success.
5. Keep the terminal available for user inspection, using documented keep-open support. Report its label and stable handle. End the coordinating turn when Orca instructs it to wait; let Orca wake the coordinator.

The worker brief must be self-contained enough to begin without the parent's full conversation:

```text
Persistent Task: <ID and TASK.md path relative to project>
Plan / attempt: <IDs; coordinator owns the plan record>
Goal and allowed edits: <specific scope, excluded shared resources>
Completion criteria: <observable conditions and evidence>
Dependencies provided: <accepted output contracts and exact evidence pointers>
Read policy: use task-runtime; open only this Task entry first, resources on demand.
Reporting: use Orca worker completion/questions protocol from the dispatch preamble.
Return: changed files, checks actually run, results, evidence references, unresolved issues.
Acceptance: <manual or automatic>; do not claim user acceptance or release successors.
```

Select the child entry only when its exact contract is needed to prepare/verify the dispatch. This does not authorize opening siblings or all resources. Workers may update their assigned Task with revision checks. They must not edit the parent's plan, accept their own work, or launch siblings. Main coordinator controls progression. Honor project permissions and the Task's design gate; dispatch is not permission to bypass them.

## 5. Completion and acceptance

Attempt transitions:

```text
prepared -> launching -> running -> reported
                   \-> failed / unknown
                               running -> failed / unknown
```

`reported` means a worker returned a result, including a failed result. Acceptance is independent and initially `pending`. A terminal exit, idle signal or successful launch is not a worker success report. An interrupted worker without a completion report requires recovery, not inferred completion.

- Manual sequential: for a successful report, inspect returned evidence, checkpoint the child as `awaiting_user`, report findings, and wait. A failed result stays blocked for repair rather than entering acceptance as a success. Only explicit user acceptance of this Subtask sets `accepted` with actor `user` and releases the next terminal. An ambiguous “继续” should not be interpreted as accepting several tasks; clarify if the target or intent is unclear. Rejection records `rejected` and keeps the successor blocked.
- Automatic sequential: the coordinator compares evidence against the frozen criteria. Set `accepted` with actor `coordinator` and basis only when supported. Missing evidence or a failure blocks progression; request a worker follow-up or user decision as appropriate. Do not turn a worker's self-assessment into automatic acceptance.
- Parallel: reported tasks are individually reviewed by the coordinator against criteria; dependencies release after accepted results. If the user requested human review for an item, preserve that gate. Report each outcome separately; one failure does not become a batch success.
- A selected Task reaches `completed` only after its required acceptance. If a worker wrote completed early in manual mode, reconcile it to `awaiting_user` with revision checking. Never rely solely on Task status to bypass the plan gate.
- A user request to fix/revisit an item records a follow-up attempt linked to the same Task and existing Orca worker when reusable. Do not overwrite prior results. Already released dependent work requires impact review when accepted outputs change.

A serial failure stops its sequence. In parallel, unaffected independent tasks may continue within the authorized batch; dependents remain blocked. A batch is finished when every selected item is accepted or legitimately skipped; failed/blocked items must remain visible as unfinished. Synchronize the parent Task at a semantic checkpoint; do not mark it completed merely because this execution batch finished if its broader goal remains open.

## 6. Recovery

On resume, load the selected parent entry, then its declared plan through budgeted context access. Recheck Git, Task revisions and live Orca state. Match by stable IDs/handles, never title alone. Follow Orca recovery references for unknown/failed workers, and coordinator references for task DAGs or several Runs. Persist the exact run binding to avoid accidentally targeting a newer default Run.

- `prepared`: verify no external launch happened before proceeding.
- `launching` or `unknown`: inspect receipts and live resources. Use supported replay IDs only according to Orca's recovery guide. Never repeat a fresh launch because no output arrived.
- `running`: reconcile the actual worker and previously handled inbox messages; await Orca wakes rather than installing polling loops.
- `reported` + pending manual acceptance: resume waiting for the user; never infer acceptance from elapsed time, a new session, or silence.
- Lost terminal: retain the attempt and evidence; distinguish a closed terminal from lost task results. Reuse/reopen through documented Orca flow when possible. An uncertain old worker must be reconciled/fenced according to Orca before replacement, not assumed dead.
- Cancellation: stop launching successors, record the user's request and confirmed runtime outcome. Do not claim cancellation stopped a worker without evidence. Do not delete terminals or workspaces automatically.

The Skill does not promise unattended progress while Orca/coordinator is unavailable. Persisted records support resumption; actual wake behavior is provided by Orca and needs live validation in the target installation.
