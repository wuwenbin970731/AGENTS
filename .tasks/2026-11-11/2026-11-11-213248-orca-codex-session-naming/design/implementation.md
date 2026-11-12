# 无打断命名接入设计

用户已批准：主 Agent 在准确 session 绑定后尽早命名；优先原生回执/事件，其次 worker 正常初始化回传，已开启索引唯一检索为备用；不向 TUI 注入命令、不 resume 接管、不阻塞业务。

## 实现契约

- 新增标准库 sessionctl.py：environment 输出执行上下文指纹；identity 从工具环境只读生成结构化绑定；name 选择/校验候选，主 Agent 经临时 app-server 元数据接口命名并回读。
- 输入是环境私有 spec（持久化 Task/attempt、原生 Task/Dispatch、唯一 marker、cwd、预期名称、环境指纹）与规范化运行时/初始化/索引证据；不从任意 Orca JSON 中猜 UUID。
- 多来源冲突、索引未启用/不新鲜/多匹配/截断/环境不符、内容身份不符时延迟/冲突，不改名。优先级不用于掩盖互相矛盾的会话 ID。
- 使用分页条目读取核对第一条任务用户消息中的原生 Task ID、Dispatch ID 与唯一 marker，并核对 cwd。不要无界加载完整历史；接口不支持时 pending。
- 主 Agent 单写环境私有 store；按 session 加短锁，原子记录 pending/setting/verified/conflict 与历史。设置前写 setting；回执不明时下次只读核对。已 verified 的同一 session 仅核验；人工改名或预期标题改变时不自动覆盖，需明确允许更名。
- 只调用 initialize、thread/read、thread/items/list、thread/name/set；不调用 thread/resume、turn/start 或 UI 输入。失败返回独立命名状态，不影响 Task 状态机。
- optional session_name 纳入计划策略和中文 Review，默认等于 terminal_title；动态 naming 状态不改变 plan digest。更新 worker brief、core-sync 复用入口及 COPY_MAP。
- 原有 README 未提交编辑与历史验证 Task 保留；不提交、推送或更新下游。

## 验证

单测覆盖优先级、冲突、索引缺失/滞后/多匹配、错误会话/环境、并发锁、一次设置/重复核验、人工改名、设置回执丢失及 RPC 超时、CLI 标准 JSON-RPC 生命周期。用既有独立仿真会话做只读/幂等验证，不碰业务 session。运行仓库全套检查与初始化 dry-run。
