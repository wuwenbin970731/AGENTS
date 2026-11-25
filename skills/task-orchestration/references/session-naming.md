# Codex 无打断命名

## 职责与时机

主 Agent 为每个 Codex attempt 准备预期名称和随机唯一 marker，负责身份校验、外部命名与结果记录。默认会话名等于已 Review 的展示名称（schema 3 的 display_title；旧 schema 2 的 terminal_title），也可在计划中明确 session_name。terminal/chat 的实际载体绑定见 [surfaces.md](surfaces.md)，Orca chat 展示名与 provider 会话名分别核验。改名字不需要子 Agent 执行自然语言请求。

拿到准确绑定后尽早设置，理想情况下在业务工作开始前；若只能初始化后取得 ID，则主 Agent 同时处理，不要求 worker 暂停。初始还没有持久化用户条目时记 pending，等正常生命周期事件/初始化消息到达后再试；不要为命名启动额外模型回合。

禁止向 terminal/chat worker 注入 /status、/rename、额外 prompt 或 resume；不通过 thread/resume 接管 writer，不改数据库或 rollout 文件。命名状态独立于执行、验收和调度：pending/conflict 不阻塞业务，也不作为 completed 的条件。

同一已验证 thread 后续只读核验；新的真实 thread 要新的 attempt/marker。正常 follow-up、resume 继续使用最初的命名绑定与 proof scope，不因 Orca 后续派发创建了新 Task ID 就把旧 first-message 身份改写。预期标题实质变化须先更新计划并 Review，再显式允许更名；已发现的人工改名不自动覆盖。

## 获取 ID 的优先级

1. **原生回执/生命周期事件**：仅当当前版本确实暴露 Codex provider thread ID、且可绑定精确 Task/Dispatch/执行主机时采用。不得从任意 UUID 字段推断；当前仿真版本回执未提供，不臆造 CLI 参数。
2. **worker 正常初始化消息**：启动 brief 明确要求一次只读 identity，通过 Orca 消息把结构化结果发送协调者，随后立即继续工作，不 ask、不等待命名完成。这是正常工具步骤，不是 TUI 控制输入。
3. **索引备用**：先确认用户已开启索引；记录当前环境 index-status 与随机 marker 查询结果。索引未 current、结果不唯一或被截断、证据超过 120 秒时 deferred；不自动开启索引、不轮询。一次事件后可重新采集，但不得用最近时间挑 session。

回执和初始化回传同时存在却不同，记冲突待查，不能用优先级掩盖矛盾。没有可靠 ID 时只记录待处理。

**thread ID 与 session 树根 ID 分开**：命名目标是可恢复的 thread.id。identity 使用 CODEX_THREAD_ID；CODEX_SESSION_ID 若存在只记录 session_root_id，fork 时二者可能不同。只有根 ID 而没有 thread ID 时返回不可用，不把根会话误当 worker。

## 私有 spec 与绑定证据

文件放在当前执行环境的私有运行目录（例如控制工作区 `.tasks/.state/session-naming/`），不把私人路径/原始回执写入版本化 Task。示例是字段结构，使用时替换占位值；environment 由下述命令生成：

```text
python3 <skill-dir>/scripts/sessionctl.py environment
```

```json
{
  "schema": 1,
  "task_id": "<持久化 Task ID>",
  "attempt_id": "<本轮 attempt ID>",
  "worker_task_id": "<Orca Task ID>",
  "dispatch_id": "<Orca Dispatch ID>",
  "marker": "<至少16字符的随机唯一标记>",
  "environment": "<本机 fingerprint>",
  "cwd": "/path/to/worker-project",
  "desired_name": "项目 · S1 · 任务标题"
}
```

marker 要放进首次业务 spec；实际 worker_task_id/dispatch_id 由 Orca 原生前导提供，coordinator 在收到派发回执后固定。worker 的身份 spec 可以用 preamble 中的准确值构造到其允许写入的私有临时目录，或由协调者在允许共享的私有控制位置提供；不让 worker 修改主 Agent 的命名 store。只读身份本身不要求读项目文件。

worker 使用该实际安装/固定源提供的 helper（没有 helper 就回报 unavailable，不现场复制一套实现）：

```text
python3 <skill-dir>/scripts/sessionctl.py identity --spec <private-spec.json>
```

stdout 是一条 JSON。只读取工具环境 CODEX_THREAD_ID 和 CODEX_SESSION_ID，不 dump 其他环境变量。协调者通过原生 Orca 消息接收，并核对发送者与准确 Dispatch 的绑定。brief 明确请求这条初始化消息，符合“不发送多余进度”的前导约定；按当前 Orca 指南 send 给 coordinator，不用 ask。初始化能力不存在时继续业务。

规范化 evidence：

```json
{
  "runtime": null,
  "worker_init": {
    "schema": 1,
    "source": "worker_init",
    "provider": "codex",
    "available": true,
    "thread_id": "<Codex UUID>",
    "task_id": "<与 spec 相同>",
    "attempt_id": "<与 spec 相同>",
    "worker_task_id": "<与 spec 相同>",
    "dispatch_id": "<与 spec 相同>",
    "marker": "<与 spec 相同>",
    "environment": "<与 spec 相同>"
  }
}
```

原生 runtime 若可用采用同一 scope/protocol 字段，source 为 runtime；不可用可省略或 available=false。不能把 Orca terminal handle、taskId、通用 orca_session_id 填到 thread_id。工具当前支持实际验证过的 UUID 格式，其他格式作为能力未支持处理。

索引证据的 index 字段包含 environment、captured_at（带时区 ISO 时间）、status（原始 index-status JSON）、search（原始搜索 JSON）。两者可直接使用包含 result 的 Orca 回执。主 Agent 搜索随机 marker 并明确限定当前环境/provider；不能只搜索通用任务标题。必须唯一 hit、snippet 含 marker、四个 truncated 标记完整且为 false/0。helper 不会自行启用或扫描索引。

## 主 Agent 调用

```text
python3 <skill-dir>/scripts/sessionctl.py name \
  --spec <private-spec.json> --evidence <private-evidence.json> \
  --store <private-shared-store> --codex <execution-host-codex-path>
```

路径均按 worker 所在实际主机解释。本地与 SSH 分别调用，不能把远端 UUID 交给本机 Codex。指纹包含主机、用户和实际 CODEX_HOME；只有回执核对主机与 workspace 后才规范化证据。不会自动换模型、升级客户端、启动/重启 daemon、改认证或全局配置。

helper 用临时 stdio App Server 调用 initialize/initialized、thread/read（metadata only）、thread/items/list（最早四项以内）、thread/name/set。核对实际 cwd 和第一条用户任务消息包含准确原生 Task/Dispatch/marker；不读取整段历史，不 resume、不提交 turn。接口/分页存储不支持、条目过大（响应预算 2 MiB）或身份不完整时 pending，不能静默降为猜测。

超时默认整个 RPC 阶段 10 秒，可设至多 30 秒；不轮询。CLI 解析错误可能非零，业务协调者仍不能把它升级成 worker 失败；业务状态机不依赖命名命令退出码。正常命名失败会以退出码 0 输出 business_may_continue=true 与独立原因。

## 状态、恢复与人工保护

store 中按 thread UUID 保存记录并加短独占锁；所有协调者要共享同一环境的 store，不能各自创建互不相关的锁目录。按 Task+attempt 保存 attempts 结果；文件原子替换、权限 0600。不存在自动抢占陈旧锁，先检查原协调进程再恢复。store 必须由单一协调协议维护，不是防恶意进程的隔离边界。

- pending：绑定缺失、环境/内容不符、索引不足、接口超时或不可用。报告“命名待处理”，业务继续。
- setting：写入设置意图后调用接口；结果不明时保持该记录，下次先读真实名称，若已经符合就核验，不重复设置。
- verified：读取实际 name 符合预期。以后复用已核验绑定记录，只读检查；不会因索引后来关闭而重新搜索或重新命名。
- conflict：已核验会话被人工改名、计划标题改变未获允许，或资源属于其他 Task。保留用户选择，不覆盖。

已核验绑定优先复用不是新的 ID 发现来源；首次发现仍按上述三档。收到同一 attempt 的新 thread ID 时要求新 attempt，而不是覆盖历史。不同 Task 不能自动抢同一个 thread 的命名记录。

标题变更获明确 Review 后，可加 --allow-name-change；该参数只允许预期标题变化，不授权覆盖检测到的其他人工名称。保存旧名/新名历史，不覆盖其他会话。接口没有 compare-and-swap 保证：工具设置前再读一次检查名称是否变化，但不能消除外部客户端在最终检查后的并发竞争；保持单协调者写入，发现人机同时改名时停止协同处理。

主 Agent 将输出关联到 attempt.naming，并把 thread_id 保存到 binding.codex_thread_id；Orca 自身的 task/dispatch/session handle 分字段保存。已打开 TUI 可能缓存旧显示，不能为刷新 UI 中断任务；后续正常恢复会读取持久化名称。

## 验证边界

此前本机 Codex 0.167.0 的普通 terminal 和真实 supervised worker 已验证：外部接口改名、名称检索、后续回合保持名称；SSH 与其他版本尚未实测。新 helper 的假服务测试验证协议与失败路径，不等于远端稳定性。其他 Agent 不调用本适配器。Codex 官方协议参考：https://learn.chatgpt.com/docs/app-server。
