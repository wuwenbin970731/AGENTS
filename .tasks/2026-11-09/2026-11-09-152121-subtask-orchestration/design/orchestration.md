# Subtask Orca 编排设计

## 已确认目标

- 独立 task-orchestration Skill，与 task-runtime 并列；AGENTS.md 只做触发与路由。
- 默认验收串行；支持自动串行与并行。并行默认全部直接子 Task，也可选定一批。
- 持久化 Subtask、terminal、Agent、Orca runtime ID 的对应关系和执行历史。
- 创建 Subtask 不等于授权启动；授权执行计划后不重复询问普通启动细节。

## 职责和实现

- task-runtime 继续管理 Task schema 5、父子关系、依赖、revision、Context Map。
- task-orchestration 定义计划、调度、验收和恢复协议；首期是 Agent 执行的 Skill，不新增常驻调度器或 Task schema。
- Orca 自带 orchestration 管理真实 worker、消息、唤醒；orca-cli 管理 terminal 表面与命名。使用版本匹配指南，不复制完整 CLI 文档。
- Task 执行记录由协调者单写，文件更新使用同目录临时文件和原子替换。Task 元数据仍使用 taskctl revision 写入。
- 项目默认偏好放在 AGENTS.md 的可选项目段。缺省模式 manual-sequential；Agent 无隐含默认；模型和 effort 仅使用明确配置或本轮指定。
- 父 Task 资源 orchestration/<plan-id>.json 保存冻结选集、顺序、策略、attempt、绑定、结果和验收。并发独立计划不能同时拥有同一个 Subtask 的活动 attempt。
- plan-id 使用时间加随机后缀；计划预留未启动 attempt 后才执行外部启动，返回不明确则标记 unknown，核对后再决定恢复。
- 用户偏好要求 terminal，不能静默使用 chat。若 worker-start 无法满足 terminal/title/keep-open 约定，按 Orca low-level-topology 指南组合 terminal 创建与 worker 绑定；不猜参数。

## 状态和语义

- attempt 状态：prepared → launching → running → reported；启动或执行失败为 failed；无法确认的外部结果为 unknown。
- reported 仅表示 worker 回报；验收记录独立为 pending/accepted/rejected。
- manual-sequential：只有明确用户验收 accepted 才推进。
- auto-sequential：协调者根据已约定验收条件和证据 accepted 才推进；不足则阻塞或返工。
- parallel：只启动选集中依赖已满足的直接子 Task；不自动展开后代、不自动补入未选中的依赖。
- 子 Task completed 必须符合验收约定；worker 提前写 completed 不释放人工验收门。
- 本轮之后新增的子 Task 不自动加入已经授权的计划。

## 范围和验证

首期修改新 Skill、task-runtime 路由、PROJECT_AGENTS.md 路由和本仓库 AGENTS.md。不修改全局受管块、初始化器或下游仓库。不启动真实 workers，不创建 worktree，不提交或推送。

验证：现有 unittest 全套；两个 Skill 的 quick_validate；taskctl doctor；diff check；初始化器在临时目标 dry-run，确认新 Skill 尚未安装到下游。检查三种模式、部分选择、依赖阻塞、启动回执丢失和重启恢复的协议覆盖。静态检查不等于真实 Orca 端到端验证。
