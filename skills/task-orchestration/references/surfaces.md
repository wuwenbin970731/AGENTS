# terminal / chat 执行载体

规划、启动或恢复双模式 worker 时读取。`mode` 表示调度策略，`surface` 表示执行载体；改变一个不隐含改变另一个。协调汇总节点不创建实例。

## 当前会话与缺省解析

新计划默认 `same`：跟随创建这份计划的当前发起会话。优先级为单节点显式选择 > 整批显式选择 > 当前发起会话。项目偏好只有在本轮 Review 明确采用后才能作为整批选择；旧模板的 terminal 偏好不能静默覆盖新缺省。

使用运行时提供的精确 caller/session 绑定核实当前种类；`agent show <orca_session_id>` 可用于核对精确 Orca 身份，`agent list` 仅用于寻找与 caller 绑定精确匹配的记录。不以 UI 当前 tab、工作目录、Agent 全局 Chat/CLI 设置或环境变量名猜测。特别是 `ORCA_TERMINAL_HANDLE` 可能承载兼容路由，存在该变量不能单独证明当前是 terminal。没有精确身份或证据冲突时，请用户一次性明确当前或目标载体；目标已全部显式给定时可规划，但外部启动仍需确认协调者回报路由。

`planctl.py resolve` 是纯本地转换，调用者负责提供已核实的当前载体，不声称它自动探测运行时：

```text
python3 <skill-dir>/scripts/planctl.py resolve <draft.json> --current-surface chat --current-source runtime_verified
python3 <skill-dir>/scripts/planctl.py resolve <draft.json> --surface terminal
```

仅接受未批准、未执行、未解析的新 schema 3 草案，输出到 stdout，不写原文件、不启动 Agent。用文件工具保存输出后再 check/render 和 Review。不重新解析旧计划；恢复、重试沿用已批准的具体载体。同一计划参照同一个发起会话；结构父节点不是新的来源会话。

## schema 3

沿用 schema 2 的完整层级、依赖及验收字段，新增：

- 顶层 `origin: {surface: terminal|chat|unknown, source: runtime_verified|user_declared|unknown}`。未知 surface/source 必须同时 unknown；不保存原始环境或私有路由。
- 顶层 `defaults.surface: same|terminal|chat` 表示本轮输入策略。
- 每个执行叶子必须有已解析 `surface: terminal|chat`、`surface_source: item|plan|current_session`、`display_title`、`agent`、`workspace`。草案中 surface 可省略或为 same；check/render/ready 不接受未解析计划。
- `display_title` 替代新计划的 terminal_title，协调汇总节点不填执行载体/展示名称。Codex `session_name` 仍单独表示 provider 会话名称，默认等于 display_title。

来源、载体和名称纳入摘要。Review 展示实际目标载体与解析来源，修改后须更新 plan_version、执行树和批准。runtime 只表示状态，不能覆盖批准的载体。

schema 2 按旧 terminal 语义、旧 terminal_title 及原摘要算法处理。schema 1 继续按原扁平协议读取。需要新能力时另建 schema 3 计划并 Review，保留历史 attempts，不自动迁移。

## 显式创建与受监督绑定

加载当前 Orca 的 `orca-cli`、`orchestration` 版本指南及 `references/low-level-topology.md`，核对目标环境实际支持的参数。已核实的本机接口提供 `agent launch --surface`，而 `worker-start --agent` 仅跟随全局设置，不足以保证已批准载体。

在既有工作区采用两阶段路径：

1. 按既有协议准备 Run、Orca Task 与 spec，先保存 prepared/launching attempt。
2. `agent launch --agent <id> --worktree <selector> --surface <已批准载体> --json`，不传业务任务正文，不使用 --focus。chat 的空会话可能尚无运行时身份：在已授权的启动流程中，使用 `--prompt` 携带一次只读初始化握手，只回报唯一 marker 和当前原生身份，不执行业务、编辑文件或启动其他 Agent。已有未登记空 chat 无可验证的原生输入入口时保留现场；是否额外创建初始化实例按本轮获批资源范围决定，不能自动增加实例。按指南选择目标环境，不能用本机帮助证明远端能力。
3. 立即保存回执的 operation ID、实际 outcome 和准确实例 handle；把 structured outcome 归一化为 chat，terminal outcome 归一化为 terminal。chat 的 `structured-agent-session-…` 是创建回执中的 UI handle，不直接视为可纳管身份。等待一次原生初始化回报，并与 `agent list/show` 的准确 `orcaSessionId`、kind=chat、workspace 核对；仅使用已登记的 `orca_session_id:<id>` canonical 地址纳管。初始化 prompt 的 journaled 只证明已登记输入，不证明 Agent 已执行或纳管成功。只按该版本公开回执结构读取，不猜 ID，不轮询或重复投递初始化输入。
4. 核对实际载体符合计划。Orca 对 chat 请求仍可能回退 terminal；不匹配时记录残留实例并暂停正文投递，不标 running、不自动另开实例、不删除现场。
5. 指南允许通过 `worker-start --task <task_id> --terminal <已核实的适用 handle> --json` 纳管已有 terminal/chat。这里的 --terminal 是兼容入口，不说明 chat 有 PTY；纳管回执的 mode=terminal 也不能覆盖原生 kind=chat 的证据。用户可查看的保留策略按资源所有权核对：原生拥有的 worker 用 keep-open，采用既有 UI 实例时 keep-open 可能拒绝 no_owned_resource，须读实际 retained/生命周期证据，不能因此重建或关闭实例。若准确登记的 canonical chat 身份仍被拒绝，保留实例并报告能力缺口，不能改成无回报 handoff 或盲目重试。
6. 保存 Run/task/dispatch 及真实实例绑定；只有实际载体匹配且受监督 dispatch 已确认后才记 running。brief 只经受监督路径投递一次。

若未来原生 worker-start 支持显式 surface，可在核实参数和同等回执校验后简化。Skill 不改 Orca 全局设置、不隐式安装/升级、不新增后台调度器。

两种载体的监督统一使用 dispatch 的 worker-show、worker-read、send 和原生 ask/reply/worker_done。不要通过 terminal send 或 /status、/rename 控制 worker。命名分别核对 Orca 展示名和 provider 会话名；命名 pending/conflict 不阻塞业务验收，但不得宣称名称已设置。chat 的展示名用原生 `chat rename --session <launch 返回的 sessionId> --name <名称>`；不要用 terminal rename。只读初始化先于业务前导时，provider 第一条用户消息可能不含 Task/Dispatch，现有 sessionctl 证明规则可能保持 pending；不能伪造 first-message 证据来通过命名检查。

已纳管 chat 也可能是没有 owned worker 的 context-only 派发：本机曾出现 dispatch-address send 拒绝 `has no worker Orca started that it can continue`，回执明确 no effects applied 并指向 worker-start。不要盲重试该 send，也不要因此新建 Agent。若原派发已明确 settled，先核对同一 canonical chat 身份仍可定位且空闲，再按回执通过独立 follow-up Task 和 `worker-start --task <follow-up Task> --terminal <同一 canonical 身份>` 续跑；保留原失败及新 Task/Dispatch。只有实际成功回报才能验收恢复路径。这是显式恢复，不是自动重试后台调度；不能用它掩盖原 ask/reply 或 owned-worker 生命周期未验证的事实。

## 状态与恢复

schema 3 独立 runtime 的每个执行叶子保存 `attempts` 列表；最新 attempt 字段：

```json
{
  "attempt_id": "<稳定 attempt ID>",
  "requested_surface": "chat",
  "actual_surface": "chat",
  "binding": {
    "backend": "orca",
    "workspace_ref": "<脱敏引用>",
    "launch_operation_id": "<返回后填入>",
    "agent_handle": "<返回的兼容实例 handle>",
    "orca_session_id": null,
    "terminal_handle": null,
    "run_id": "<返回后填入>",
    "task_id": "<Orca Task ID>",
    "dispatch_id": "<返回后填入>"
  }
}
```

未返回的字段可省略。actual_surface 只取自实际回执；chat 不填 terminal_handle。terminal 的 Orca session ID 可能晚到，不强求启动时已有。provider thread ID 存 naming，不能混用 Orca session ID、handle、Task 或 dispatch ID。

创建成功、绑定失败时保留最新 attempt 的资源；pending 且已有资源也不能重新 launch，先核查并复用。计划工具校验 running/reported 的最新 attempt 载体匹配及 dispatch 绑定，防止本地记录把 fallback 当成功；它不检查真实进程、回执真实性或代理是否退出。launching/unknown 和恢复跟随 Orca 回执，使用给出的 replay ID/恢复命令，不因沉默或超时新建实例。新 retry attempt 只能在旧实例已按原生恢复协议处置后记录，不能以空 attempt 绕过旧资源核对。

来源会话关闭、换载体或协调者换会话不重新解析目标，恢复时固定原 Run 身份。连接丢失不代表结果丢失，worker 回报不等于验收通过。原始回执及私有路由放环境私有状态；Task 和可版本化计划只存最小脱敏引用。

## 验证边界

纯本地解析/状态校验与真实 Orca 启动证据分开记录。本机版本匹配指南证明了上述接口路径，但不证明每台主机、每个 Agent、chat handle 纳管、跨载体唤醒或 Codex 命名已实测。真实验收应覆盖四种来源/目标组合、默认跟随、回报和中断恢复；无法覆盖的组合保持未验收。真实 smoke worker 先按 visual-review 的具体执行树规则获批。
