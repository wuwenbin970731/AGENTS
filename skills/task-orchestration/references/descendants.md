# 后代 Subtask 编排协议

## 使用范围与工具

用户可以选择“仅直接子任务”“整个任务树”或“指定后代分支”。普通创建仍使用 task-runtime。直接子任务的既有 schema 1 记录可继续按原协议恢复；后代编排使用 schema 2，不静默升级历史记录。

`planctl.py` 是 Python 标准库实现的本地校验与调度辅助工具，不启动 Agent，不写入状态，不管理后台进程。Skill 主 Agent 仍负责持久化、Orca 调用、证据检查和用户沟通。

```text
python3 <skill-dir>/scripts/planctl.py check <plan.json>
python3 <skill-dir>/scripts/planctl.py render <plan.json>
python3 <skill-dir>/scripts/planctl.py ready <plan.json> --state <state.json>
```

`check` 校验结构与组合依赖，输出策略摘要；不证明任务可立即启动。`render` 输出中文 Markdown 执行树和详细表格。`ready` 返回当前 `launch`（执行叶子）、`aggregate`（主 Agent 汇总检查）、`accept`（等待对应验收者处理）、`blocked` 和 `batch_complete`。字段名保留英文，展示给用户时转为中文。

## 发现与计划

1. 使用有深度/数量边界的 `taskctl tree/children` 获取 Meta。发现更深节点时逐层查询；检查 `remaining_count` 及边界节点的 `child_count`，禁止把深度截断误当成叶子。任一直接子列表未完整获取时，不能声明该分支覆盖完整；拆分批次或继续有界查询。
2. 只为实际调度或汇总检查需要的准确契约读取对应 Task 入口；不批量加载所有后代正文。`tree` Meta 不含全部依赖/revision 字段，使用所选节点的 `taskctl show` Meta 获取，不根据标题猜测依赖。
3. 在 schema 2 中逐节点记录完整的 `known_children`（现场核对的全部直接子 ID）与有序的 `children`（本轮选中的直接子 ID）。选中后代须保留到本轮根的祖先链；不能把孙节点直接挂成根的孩子。脚本只校验输入一致性，协调者必须对照真实 Meta 核对层级、子列表、依赖与 revision，不能伪造完整覆盖。
4. 根默认验收串行，各节点 `mode` 省略时继承父层模式；显式指定可以覆盖。`children` 顺序就是串行顺序。并行只推进选集内已满足依赖的分支。
5. 有选定 children 的节点负责协调汇总，不新建 terminal。无已知 children 的叶子负责执行，必须明确 `agent`、`terminal_title`、`workspace`。父节点的独立编码工作应拆成一个显式、无重叠的叶子 Subtask，本版不把同一节点同时当作 worker 和协调节点。
6. 可以选取部分后代分支；未选子节点显示在执行树中。`complete` 由全体已知子节点是否选中、子树是否完整覆盖自底向上计算；部分覆盖的汇总验收只代表本轮批次，不得把整个 Task 写成 completed，也不得释放要求其完整交付的依赖。

计划最多 1000 节点、64 层；超限拆分为明确批次。发现过程仍服从 taskctl 每次查询自身边界，不做无限递归读取。

## Schema 2

参照 [example-plan.json](example-plan.json)。示例 ID 为演示符号，使用时必须替换为稳定 Task ID（`subtask_key` 仅展示）。示例选择 Codex 不构成项目默认 Agent。

顶层字段：

| 字段 | 含义 |
|---|---|
| schema | 固定为 2；不改变 Task schema 5 |
| plan_version | 策略版本，实质改变时递增 |
| revision | 计划记录写入版本，不参与策略摘要 |
| root_task | 本轮根 Task 的稳定 ID，可以是原树任意父节点 |
| nodes | 本轮根及包含祖先链的选集，逐节点定义 |
| external_dependencies | 未选入的显式依赖，键为稳定 Task ID，含 completed 与核对依据 basis |
| review | status、plan_version、plan_digest、artifact、basis，批准时 status 为 approved |
| authorization | state 为 authorized、basis 记录执行意图依据 |

逐节点字段：`task_id`、`subtask_key`、`title`、`task_revision_at_plan`、`children`、`known_children`、`depends_on`、`completion_criteria`。按需添加 `mode`；叶子必须补 `agent`、`terminal_title`、`workspace`，Codex 可选 `session_name`，缺省与 terminal_title 相同；它是持久化会话名，不能只重命名终端标签代替。模型与 effort 仅在明确选择后填写。按既有协议在独立状态资源中保存 `attempts` 及 bindings，脚本不从标题推断实例。

可选 `acceptance_actor: user` 为自动串行/并行里的某项增加人工验收；不得设置 coordinator 来绕过上层验收串行。本轮根的最终汇总默认也由用户验收。

`plan_digest` 由除 review、authorization、revision、runtime 外的完整计划计算。实质变化使旧批准失效；不要把动态回执或 attempts 放进节点策略，执行 attempt 历史放在独立状态资源中。为避免循环摘要，策略摘要只保存在 review 和状态记录中，不作为计划其他顶层字段。

## Review 与执行状态

保存 `orchestration/<plan-id>.json` 和 `orchestration/<plan-id>-state.json`，均在选中根的 Context Map 显式登记。仍沿用短锁、revision 检查和原子替换协议，由单一协调者写入。状态至少包含：

```json
{
  "plan_digest": "<check 返回的摘要>",
  "revision": 1,
  "nodes": {}
}
```

首次执行可以显式空 nodes；恢复已有执行时必须读取其旧状态并核对 Orca，不得重建空记录来绕过重复启动检查。

每个节点状态包含：

```json
{
  "phase": "reported",
  "outcome": "succeeded",
  "evidence": ["evidence/checks.md"],
  "acceptance": {"status": "accepted", "actor": "user", "basis": "用户明确验收该节点整体"},
  "attempts": []
}
```

- phase：pending、launching、running、reported、failed、unknown。prepared attempt 尚未触发外部操作，对应节点仍 pending；启动前先持久化 launching。
- outcome：reported 时必须为 succeeded 或 failed。仅 succeeded 且证据满足验收条件才可 accepted。
- acceptance：pending、accepted、rejected；actor 为 user 或 coordinator，依据必须可追溯。记录时间和精确批准依据，不能凭沉默或 worker 自评编造验收。
- attempts：沿用执行协议中的稳定 attempt ID、Orca bindings、实际回执、时间、结果与恢复历史。不要丢弃之前的 attempt。`planctl` 不验证回执真实性，须在真实 Orca 环境核对。

执行循环：

1. `check` → `render`，保存中文 Review 快照并展示；用户批准具体版本后记录 review 和执行授权。
2. `ready --state`：没有对应摘要的批准/授权时，不返回执行动作。策略与状态摘要不符时直接失败，须先人工对照已有状态重建映射并 Review 新版；不得简单覆盖摘要后重用旧验收。
3. 只为 `launch` 内叶子准备/启动 Orca worker。先排除跨计划活动 attempt、实时编辑冲突及其他环境阻塞。`ready` 不是外部副作用授权或文件冲突检测器。多叶子获准同时启动时，逐一记录回执再继续；不要在多个协调者间共享一次过期计算。
4. worker 回报后写 reported 与证据。`accept` 表示需要检查/验收，不是工具自动验收。actor=user 时明确等待用户；actor=coordinator 时对照 completion_criteria 检查后记录。
5. `aggregate` 内父节点由主 Agent 检查选中子结果、集成与自身验收标准，写 reported 后再走其上层验收门。子节点全通过并不自动 accepted 父节点。部分覆盖也可形成批次汇总，但 `task_completion_allowed=false`，必须保留整个 Task 未完成。
6. 每次变更后重算前沿。验收串行只放行下一个同层分支；分支内部依其自身模式运行。顶层选择 S1 后，S1 内部并行，不妨碍顶层等待 S1 整体验收后再进入 S2。
7. `batch_complete` 仅表示本轮根已通过其汇总验收；根的覆盖不完整时，仍不能完成整个根 Task。同步 Task 状态前检查 `task_completion_allowed`、完整任务契约和已有真实状态。

## 依赖与失败

进入某节点需同时满足：父分支已进入、同层串行前项已验收、该节点显式依赖已验收。指向聚合父节点的依赖等待该父节点整体验收，不能被任一叶子完成替代。

工具把“进入”和“验收”建成阶段图，并加入父子汇总、串行与显式依赖边，启动前判环。祖先依赖后代、后代依赖祖先、较早串行分支依赖较晚分支等死锁都应被拒绝，而非等运行后卡住。部分覆盖节点不能充当完整 Task 的依赖目标。外部依赖不自动加入选集；未完成时阻塞依赖者。

失败、unknown、验收拒绝均不自动重启或放行依赖。并行中无关分支可以继续，串行后项停留。按 Orca 恢复协议核对旧 attempt，再决定跟进或新建 attempt；不能把状态手工清空来伪造待启动。已验收交付发生返工时检查下游影响，受影响的派生验收必须重新评估，不能保留失效的父层通过记录。

迁移 schema 1 时保留原计划与历史，映射真实 Task ID、层级和 attempt，生成新 schema 2 计划与状态；对变更后的范围/角色/验收方式重新 Review。工具不自动迁移或推测历史验收。
