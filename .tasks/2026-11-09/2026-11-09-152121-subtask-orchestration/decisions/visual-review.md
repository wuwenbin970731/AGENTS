# 可视化 Review 与后代编排需求

用户确认：执行方案应提供可视化执行树供 Review；在复杂编排可解释之后，可以考虑加入后代 Subtask 编排。

本次落盘：
- 首次启动前展示与结构化计划同源的执行树，保存具体版本与用户 Review 记录；不将执行意图视为已 Review 具体方案。
- 展示选择范围、逐层策略、执行/协调角色、顺序/并行组、依赖、人工/自动验收点、Agent 和 terminal。
- 已获批且未实质改变的方案不重复确认；实质调整策略需要新版本和重新 Review，状态变化不需要。
- 后代编排记录为后续设计方向：逐父节点模式、继承/覆盖、父节点汇总、边上的验收语义、跨层依赖及部分选集边界。
- 当前只调度直接子 Task；本次未启用后代调度，不声称可视化可以保证执行无误。

权威 Skill 说明：skills/task-orchestration/references/visual-review.md。

验证：本轮重新运行 28 项 unittest 全部通过；两个 Skill 校验通过；taskctl doctor 为 0 errors/0 warnings；git diff --check 通过。未启动真实 worker，未实现后代调度或专用可视化渲染器。
