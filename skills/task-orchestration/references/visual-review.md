# Visual execution-tree Review

## Current requirement

Before launching an execution plan, provide a visual execution tree for user Review. This applies to both direct-child and multi-level orchestration. A launch request alone does not replace Review of a concrete plan. Approval of the exact displayed plan together with execution intent is sufficient; do not ask a second time for the same launch scope.

Use a readable annotated text tree or Mermaid in the conversation. For a larger plan, an HTML view may supplement the tree, but the user must be able to inspect all selected nodes and gates without truncated or hidden branches. Do not add a renderer dependency for a simple tree. No particular visualization proves scheduling correctness.

Generate the tree and its annotations from the same resolved plan used for execution. Save a snapshot at `orchestration/<plan-id>-v<plan-version>.md` and register its exact path in the parent's Context Map. The snapshot is a derived Review artifact, not a second source of execution state. The existing taskctl graph shows Task relationships/status only; do not claim that unmodified output represents scheduling policy or approval.

## 中文展示约定

面向用户的执行树、表格、节点说明、图例、状态、结果摘要和验收提示尽可能使用中文。展示名称与底层标识分离，优先采用：

| 底层值 | 用户展示 |
|---|---|
| manual-sequential | 验收串行 |
| auto-sequential | 自动串行 |
| parallel | 并行 |
| coordinator / aggregate | 协调汇总 |
| execute | 执行 |
| pending review | 待审阅 |
| awaiting acceptance | 待验收 |
| accepted / rejected | 验收通过 / 验收未通过 |

根据上下文区分“方案已批准”和“结果验收通过”，不要混用。任务标题、terminal 可读名称优先使用中文；已有用户命名不擅自翻译或更名。Task ID、S1.1 等编号、命令、路径、程序字段、枚举值和运行时标识保留原值，必要时附中文解释。此约定只改变展示，不改变接口或持久化 schema。

## What the user reviews

Show, directly on nodes or in a linked compact legend/table:

- Stable Task ID/key, short title, inclusion/exclusion and selection boundary.
- Each parent's effective mode: manual sequential, automatic sequential or parallel; label inherited versus overridden modes when applicable.
- Coordinator/aggregate versus execution role, and which nodes actually create terminals.
- Serial order and parallel groups, human acceptance gates and automatic evidence-check gates. Plan Review approval and result acceptance are separate events.
- Dependencies, including cross-branch constraints that a containment tree alone cannot show; expose unresolved dependencies, cycles, conflicting edits and other blockers before dispatch.
- Resolved Agent, explicit model/effort if any, terminal name and workspace placement for execution nodes. Never fabricate private runtime handles before launch.

Do not present a truncated tree as complete. Use bounded Meta queries; if the limit prevents a complete plan, split into explicit batches or mark the Review incomplete and do not launch hidden work.

## Review lifecycle

1. Resolve and freeze the concrete selection, ordering, mode, roles, criteria, Agent, naming and placement. Check dependencies and edit scopes before requesting Review.
2. Persist the plan with `plan_version`, review `pending`, and a snapshot for that version; present the visual and explain its progression in a few sentences.
3. Record explicit user approval with the reviewed version/artifact and a short basis. Only an approved, authorized version can launch. Approval of this Skill design is not approval of any future Task execution tree.
4. Material changes to selection, mode, dependencies, roles, acceptance criteria, Agent/model, naming convention or workspace placement require a new plan version, regenerated visual and Review before affected new launches. Preserve earlier snapshots/approval history; do not overwrite them.
5. Normal progress, returned handles, timestamps and Task revision increments do not require a new strategy Review. A predeclared retry may follow the approved recovery policy; a retry that changes execution scope or leaves an old worker uncertain must be reconciled first.
6. A strategy change does not itself cancel running workers. Record the proposed change and its impact; continue only within existing authorization until the affected plan is approved and runtime state reconciled.

## 后代编排的执行树

后代调度使用 [descendants.md](descendants.md) 的 schema 2 计划和 `planctl.py`。`render` 从同一计划生成中文执行树；`ready` 结合已记录执行状态计算前沿。图像展示、调度计算和真实 Orca 执行的证据边界分别说明。

A multi-level strategy attaches a scheduling policy to each parent, composing an execution tree rather than one global mode:

```text
主任务                       [验收串行；协调汇总]
├── S1 后端                  [并行；协调汇总]
│   ├── S1.1 接口            [执行；Agent 与终端见图例]
│   ├── S1.2 数据处理        [执行；Agent 与终端见图例]
│   └── 验收点：汇总检查 S1 后，等待用户验收 S1 整体
└── S2 前端                  [自动串行；协调汇总]
    ├── S2.1 页面            [执行]
    ├── 检查点：S2.1 证据检查通过后，才启动 S2.2
    ├── S2.2 交互验证        [执行]
    └── 验收点：汇总检查 S2 后，等待用户验收 S2 整体
```

Here Root's policy controls advancement from S1 to S2. S1's policy controls its children: their checked results roll up into S1, whose overall result is then accepted by the user at Root's gate. S2's children progress through automatic checks, and S2 itself again waits for user acceptance at Root. User acceptance of S1 does not imply each leaf needed a separate user gate.

生效的层级规则（字段与边界详见后代编排协议）：

- Root defaults to manual sequential; unspecified nested modes inherit their parent's effective mode, with explicit per-parent overrides.
- Parents with selected children coordinate/aggregate/check; selected leaves execute. The main coordinator handles aggregate nodes by default; they do not automatically get separate Agents or terminals. A parent doing independent implementation requires an explicit, non-overlapping execution scope.
- Acceptance is on an edge: the parent's policy determines how a child's result releases siblings. A parent's own completion additionally requires its selected children, aggregate criteria and its upstream acceptance gate; children succeeding alone does not complete the parent.
- Excluded descendants and required unselected work must remain visible. A partial selection cannot claim completion of an entire parent without satisfying that parent's full contract.
- Cross-level dependencies target stable Task identities and release only after the referenced node's required acceptance, not on a descendant's individual completion.
- Discover descendants through bounded Meta traversal and load exact entries only for dispatched/checked contracts. Do not conflate recursive scheduling with recursive context loading.

后代调度前必须通过计划结构和组合依赖校验，并检查对应版本的可视化 Review、执行授权与持久化验收状态。可视化帮助审查；依赖校验、实时回执核对和验收门仍不可省略。`ready` 只给出本地调度判断，不会启动真实 worker。
