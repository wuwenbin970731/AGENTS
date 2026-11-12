# 真实 Orca supervised Subtask 命名仿真

## 授权和范围

用户要求以实际 orca-cli 创建 Subtask 走完整流程，并询问稳定性。采用本机真实 Run、worker-start --agent codex 和原生前导 prompt，正常工具调用和 Orca 消息回报；不使用 /status、/rename、terminal send、terminal read 或重新 resume 来介入 worker。不改生产编排、全局设置或业务文件。

## 执行与证据

- 新建独立 Orca Run 和一个持久化 S1 Subtask。第一次启动在 account/read 的 workspace routing discovery 阶段失败；Orca 明确证明启动命令退出且 Task 未执行。
- 按失败回执 worker-release 释放该终端成功；对同一 Orca Task 用 retry-of 重试，进入 ready/input_accepted。没有创建替代 Task 绕过失败。
- Orca 唤醒后读取 worker_done。worker 只读工具环境的 CODEX_THREAD_ID 与 CODEX_SESSION_ID，返回相同值；没有读写项目。
- worker-read --source transcript 返回 sourceExact=true，首条用户消息先包含 Orca 固定派发文案，随后才有实际任务。该接口文本会截断，不能把 sourceExact 当成文本完整性保证。
- 主 Agent 只读检查到 Orca 会话索引 enabled=true。搜索本次随机唯一标记，唯一命中一个 Codex session；候选/查询/新鲜度均未截断。该 ID 与 worker 工具环境 ID 一致，结果附 resumeCommand。
- 通过 App Server thread/read 读取这个候选，核对完整前导前缀逐字一致、准确 Task ID、唯一随机标记同时匹配；不是按最近时间或标题猜测。初次要求完整文本相等的检查因 Orca 文本被截断而停止，没有误改会话；之后明确改为完整可见前缀及强标记联合匹配。
- 经 thread/name/set 从主 Agent 外部改名成功，thread/read 与 thread/list 可读新名称。未向 worker TUI 输入命令，未抢占 writer。
- 使用 Orca orchestration send 对同一保留 terminal 发起正常后续仿真。Orca 新建 follow-up Task/Dispatch（不等同于原 Orca Task），底层仍为同一个 Codex session；worker_done succeeded 后，独立 App Server 再读名称仍未被后续前导输入覆盖。

## 脱敏结果

- 原名称：Await coordinator instructions
- 新名称：AGENTS · S1 · 无打断会话命名仿真
- Codex session ID：`01a1cadf-cc77-7e03-b1bb-513be3327006`
- 后续回合名称仍一致：True

## 稳定性结论

当前证实的是一个本机样例及后续正常回合，不是生产稳定性保证。命名 API 机制可行；依赖索引的外部 session 发现有条件：需要索引由用户开启、及时覆盖该会话、唯一标记可查且全部身份校验通过。关闭/延迟/多匹配/截断/其他主机都必须视为未核验，不自动开启索引，不碰运气改名，不阻止业务继续。

更可控的生产主链路：Orca 若能直接暴露 provider session ID，优先使用其与 Dispatch 的权威绑定；现有 CLI 的本次回执/worker-show 未直接提供。当前可选替代是 worker 正常启动初始化时，通过结构化 Orca 消息回报工具环境的 CODEX_THREAD_ID，并联合 Task/Dispatch/标记验证，再由主 Agent 外部改名。该环境变量只验证了当前版本，仍要能力检查，不承诺所有版本必有。索引检索作为已开启环境的补救路径。

未验证并发多个同名 worker、索引关闭路径、SSH、多版本及异常恢复；不宣称整个自动命名流程已稳定。未修改 Codex 数据库/rollout，未删除任何会话。成功测试 worker 依 keep-open 保留供用户复核；失败启动终端已按明确恢复回执释放。
