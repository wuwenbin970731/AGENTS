# 后代调度验证

## 结果

- 新增 planctl.py：校验 schema 2 层级计划及阶段依赖图；从同一策略渲染中文 Review 树；根据显式状态计算启动、汇总、验收前沿。
- 更新 Skill、执行协议、可视化要求与项目模板，启用明确范围内的后代编排，保留 schema 1 历史恢复方式。
- 自带 example-plan.json 为 7 个虚构节点，不含实际运行环境或启动授权；example-review.md 是其派生演示快照。

## 实际检查

- python3 -m unittest discover -s tests -v：49 项通过（原有 28 + 新增 21），21.490 秒。
- 最后中文渲染细节调整后，重跑新增 21 项：全部通过。
- 新增测试覆盖混合三种模式、四层继承/覆盖、父节点汇总与人工验收、跨分支依赖、串行/层级组合死锁、部分覆盖、外部依赖阻塞、过期 Review/状态、运行中/失败/unknown 不重复启动、人工验收覆盖、CLI 同源渲染等。
- check 示例计划：7 节点通过；render 生成中文 Markdown 快照。
- 两个 Skill quick_validate：通过（PyYAML 仅使用临时目录安装）。
- taskctl doctor：0 errors，0 warnings。
- git diff --check：通过。

## 边界

这是本地计划校验、调度判断与 Skill 协议完成，不是 Orca 端到端验证。未启动真实 worker、创建 terminal/worktree、更新下游仓库或修改初始化器；未提交或推送。

工具不会读取真实 Meta、操作 Orca、验证外部回执真实性、检测文件编辑冲突或写入验收记录。协调者必须核对实际 Task 层级、依赖与 revision，按 Review/单写协议持久化状态，并依据真实回执和用户验收推进。旧状态不得以空记录替代。后台唤醒仍由 Orca 提供。
