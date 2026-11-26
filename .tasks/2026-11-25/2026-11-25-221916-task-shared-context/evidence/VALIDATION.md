# 实现验收

## 结果

已实现 context shared-list/read/check/write，以及 Runtime Skill、加载协议、schema 说明、生成入口、模板、自用副本、PROJECT_AGENTS 和 README 的工作流说明。
本 Task 的 CONTEXT.md 已通过 shared-write 首次创建，revision 从 4 递增至 5，随后 shared-read 成功加载，shared-check 返回 changed=false。

## 实际验证

- `python3 -m unittest discover -s tests -v`：125 项通过，210.312 秒。该轮发现测试后新增了一个测试，因此另跑最终 Runtime 测试集，覆盖新增项。
- `python3 -m unittest discover -s tests -p test_task_runtime.py -q`：最终版 34 项通过，23.702 秒。包括锁冲突和读取期间变更拒绝；运行后未再修改运行时代码或测试。
- Runtime 场景覆盖：深层祖先来源、保留父定义与局部例外、兄弟隔离、不披露祖先入口、发现不输出约定、父级更新及文件创建/删除的指纹变化、总预算与 UTF-8 错误、SHA-256 和 revision 双重冲突保护、锁冲突、读取中变化、符号链接和异常祖先链。
- skill-creator quick_validate：Skill is valid!，无需安装额外依赖。
- taskctl doctor：15 个 Task，0 errors，0 warnings。
- TASK_WORKFLOW、TASK_TEMPLATE、TASK_ITERATION_TEMPLATE 与 .tasks 自用副本逐个字节一致；taskctl 可执行位保留。
- 临时空项目执行初始化器 dry-run：exit 0，apply=false，返回 plan_digest，目标目录未写入。自动化测试另覆盖真实临时安装与 CLI 行为。
- git diff --check：通过。

## 证据边界

- CLI 不理解自然语言冲突；测试验证保留来源及双方原文，冲突消解由 Skill 约束 Agent 在依赖工作前完成。
- 读取整链不是跨文件事务；输出前复核内容指纹。资源与入口分两次原子替换，发生中断时需复查实际文件；直接编辑器不受 CLI 锁保护。
- 默认 32 KiB 限制是总正文预算，JSON 包装另计。祖先链超过 100 节点明确拒绝，不截断。
- 保持 schema 5 和旧任务兼容，没有批量创建空 CONTEXT.md，没有同步下游或全局规则，没有提交、推送。原有未跟踪文件未覆盖。
