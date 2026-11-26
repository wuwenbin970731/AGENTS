# Progressive Task Loading Protocol

## Contents

1. Storage boundaries
2. Selection state machine
3. Disclosure levels
4. Recursive task traversal
5. Derived HTML graph views
6. Resource budgets
7. Checkpoint writes
8. Session and concurrency behavior
9. Legacy compatibility
10. Shared Task agreements

## 1. Storage boundaries

- Versionable task content lives in `<project-root>/.tasks/`.
- A root task lives at `.tasks/YYYY-MM-DD/<task-id>/TASK.md`; a schema 5 child lives below its parent at `subtasks/<task-id>/TASK.md`.
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
| L0 | Frontmatter metadata | Task search, relation lookup, or bounded tree traversal |
| L1 | Selected `TASK.md` | Current task resolved |
| L2 | Current design, runbook, or decision | Context Map condition matches current work |
| L3 | Iteration, evidence, or archive | A specific conclusion must be traced or verified |

Opening one level never recursively opens the next. Other tasks remain at L0 unless their contract directly affects the current decision. After selection, the shared-agreement exception below authorizes only ancestor `CONTEXT.md` files, never ancestor entries or arbitrary resources.

## 4. Recursive task traversal

- `children` returns direct children only and defaults to eight results.
- `tree` defaults to depth one and a 20-node output budget. It has an implementation-level maximum depth and item limit; storage depth itself is not hard-coded.
- `lineage` returns only L0 ancestor breadcrumbs and the selected task.
- A parent entry never embeds complete child entries or status histories. Aggregates such as `child_count` are computed from Meta.
- Selecting a child promotes only that child to L1. Ancestors, siblings, and descendants remain at L0 until separately selected, apart from the reserved ancestor CONTEXT.md exception in section 10.
- A Context Map resource cannot enter `subtasks/` or any directory governed by a descendant `TASK.md`.

## 5. Derived HTML graph views

`graph` renders the same bounded L0 subtree as a single-file HTML snapshot through `answer-me-with-html`. It defaults to depth three and at most 100 nodes, while retaining the implementation maximum depth of eight and maximum node count of 100.

The selected Task directory is the output boundary. Relative paths resolve from that directory; output cannot escape it or enter `subtasks/`. The default is `evidence/task-graph.html`. Rendering uses a same-directory temporary file and replaces the target only after success.

The page is a derived view, never task truth. It shows the stable hierarchy key, status, checkpoint, direct child count, bounded status totals, and any remaining node count. It never reads Task bodies or Context Map resources. Register the exact HTML path in the current Task's Context Map only when agents need to load it as evidence.

`answer-me-with-html` is optional. The runtime can discover an explicit `--am-cli`, `ANSWER_ME_WITH_HTML_CLI`, a global `am`, or common user-level Skill locations. If no renderer is available, fail without changing an existing page and keep `tree --format json` available.

## 6. Resource budgets

`context list` reports `size_bytes` and a conservative `estimated_tokens` for every valid resource without reading its content. Byte size is the deterministic boundary; token estimates depend on the model and are only planning hints.

`context read` has a default 32 KiB limit and accepts an explicit byte or token budget. It rejects oversized content before emitting it and never silently truncates. Large resources should be split by stable topic or section and declared separately in the Context Map.

## 7. Checkpoint writes

Write current state at semantic checkpoints rather than every message or code edit. `TASK.md` contains task contract, current work state, Context Map, and dependency contract. Keep detailed or append-only evidence in declared resources.

Update a resource first, then update the task entry, increment `revision`, and refresh the local session's seen revision. Filesystem writes must use same-directory temporary files followed by atomic replacement.

## 8. Session and concurrency behavior

A task may be bound to several sessions; a session has at most one current task. Binding is a local hint, not ownership. Hold a task lock only during the final write. Compare the revision read at work start with the current revision under the lock. On mismatch, stop with a conflict and merge from the current entry.

Lock files older than five minutes may be treated as stale. A lock must never be held for a whole conversation.

Automatic `subtask_key` allocation and child-directory creation hold the parent lock only during allocation and creation. Updates to a child use the child's own ID lock and revision.

## 9. Legacy compatibility

Schema 4 tasks remain writable in their existing flat locations and participate in virtual trees through `parent_task`. Schema 2/3 tasks remain readable; their `active_iteration` is compatibility metadata and is not automatically loaded. Upgrade only an active or reopened task, preserve its ID and history, and never bulk-move historical tasks merely to normalize layout.

## 10. Shared Task agreements

`CONTEXT.md` is optional and created only for confirmed stable definitions, parameters, scope or premises. It is not progress, logs or unconfirmed design. Its conventions govern the owner and descendants. Children can add local agreements; conflicting inherited meanings require an explicit exception naming source, reason and scope. No implicit nearest-file override, sibling inheritance or automatic semantic merge. Cross-tree sharing remains an explicit dependency.

After selection/resumption, use `context shared-list <task>` followed by budgeted `context shared-read <task>`. Before execution and acceptance, compare the fingerprint returned by the last successful read with `context shared-check <task> --expect-fingerprint <hash>`. Exit 3 means changed: reload and assess impact; a listing/check alone does not count as loading the new version.

These JSON commands traverse exact parent IDs root first (including schema 4 virtual parents), reject cycles, missing/duplicate parents, and fail beyond 100 nodes rather than omit ancestors. They never disclose ancestor TASK bodies or follow links inside agreements. Each source has owner ID, project-relative path, existence, SHA-256, byte count and estimated tokens. Missing files participate in the fingerprint so later creation/deletion is visible. shared-list hashes bytes in chunks without returning content; it is not a metadata-only discovery command. shared-read returns existing sources with content and a whole-chain fingerprint. The body budget is total across all files (default 32 KiB, tokens estimated at 3 bytes each); JSON envelope is additional. No partial content is emitted on errors. Recheck the chain before emission; this detects changes during reading but is not a multi-file filesystem transaction. Symbolic links and non-regular shared files are rejected.

CONTEXT.md is a reserved, fixed-name shared resource, exempt from per-task Context Map registration only via these commands. Ordinary context read retains its declaration and path checks. No schema migration or empty-file backfill is needed. Detailed supporting documents still require Context Map conditions.

`context shared-write <owner> --from <file> --expect-sha256 <hash-or-missing> --expect-revision N` rejects blank content and writes only the selected owner's local file. It checks both content SHA-256 and Task revision under that Task's short lock, atomically replaces CONTEXT.md, then increments TASK.md revision. Conflict exits 3; lock contention exits 4. Cooperating CLI writers are serialized; direct editor writes do not honor this lock and must be coordinated. The two file replacements are not a transaction: after interruption inspect both files; content fingerprints, not revision alone, determine whether agreements changed. Never silently rewrite an ancestor from child work. This command does not interpret or validate natural-language exceptions: the agent must explicitly resolve those before dependent work.
