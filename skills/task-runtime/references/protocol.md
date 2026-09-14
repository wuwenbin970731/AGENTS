# Progressive Task Loading Protocol

## Contents

1. Storage boundaries
2. Selection state machine
3. Disclosure levels
4. Checkpoint writes
5. Session and concurrency behavior
6. Legacy compatibility

## 1. Storage boundaries

- Versionable task content lives in `<project-root>/.tasks/`.
- One task lives at `.tasks/YYYY-MM-DD/<task-id>/TASK.md`.
- Project-local runtime state prefers `<absolute-git-dir>/task-state/`; for a non-Git project or a sandbox that denies Git-directory writes, it falls back to ignored `.tasks/.state/`.
- Session files, locks, and caches are not task truth and must not be committed.
- `TASK.md` frontmatter is the only authoritative metadata source. Any future index is a disposable cache.

## 2. Selection state machine

Resolve the current task in this order:

1. Explicit ID or path from the user.
2. Valid local session binding whose goal still matches.
3. Metadata search over open tasks, limited to eight results.
4. New task creation after confirming no existing task shares the goal and completion boundary.

Never scan task bodies to choose candidates. Do not search tasks for `light` work.

## 3. Disclosure levels

| Level | Content | Entry condition |
|---|---|---|
| L0 | Frontmatter metadata | Task search or related-task lookup |
| L1 | Selected `TASK.md` | Current task resolved |
| L2 | Current design, runbook, or decision | Context Map condition matches current work |
| L3 | Iteration, evidence, or archive | A specific conclusion must be traced or verified |

Opening one level never recursively opens the next. Other tasks remain at L0 unless their contract directly affects the current decision.

## 4. Checkpoint writes

Write current state at semantic checkpoints rather than every message or code edit. `TASK.md` contains task contract, current work state, Context Map, and dependency contract. Keep detailed or append-only evidence in declared resources.

Update a resource first, then update the task entry, increment `revision`, and refresh the local session's seen revision. Filesystem writes must use same-directory temporary files followed by atomic replacement.

## 5. Session and concurrency behavior

A task may be bound to several sessions; a session has at most one current task. Binding is a local hint, not ownership. Hold a task lock only during the final write. Compare the revision read at work start with the current revision under the lock. On mismatch, stop with a conflict and merge from the current entry.

Lock files older than five minutes may be treated as stale. A lock must never be held for a whole conversation.

## 6. Legacy compatibility

Schema 2/3 tasks remain readable. Their `active_iteration` is compatibility metadata and is not automatically loaded. Upgrade only an active or reopened task, preserve its ID and history, and add schema 4 metadata plus a Context Map without rewriting historical resources.
