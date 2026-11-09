# 首版验证

- python3 -m unittest discover -s tests -v：28 tests，全部通过。
- task-runtime：按仓库指定 TRAE quick_validate 校验通过。
- task-orchestration：Codex skill-creator quick_validate 校验通过。
- 两个校验器原环境均缺 PyYAML；安装到临时目录，通过 PYTHONPATH 运行。未增加项目依赖。
- taskctl doctor：4 tasks，0 errors，0 warnings。
- git diff --check：通过。
- 初始化器临时目标 dry-run：apply=false，新 Skill 未出现在安装 action 中。只改项目模板入口，未修改 COPY_MAP；未应用任何下游更新。
- 协议人工检查覆盖：验收串行、自动串行、并行全部直接子 Task/子集、有界查询截断、依赖和顺序冲突、重复 attempt、启动回执不明确、恢复待验收状态。

## 证据边界

没有启动真实 worker、创建 terminal 或 worktree。没有进行 Orca 端到端测试。现有 unittest 只证明仓库原有行为未出现已测回归，不证明新编排流程的实际运行效果。新 Skill 是 Agent 执行的协议；计划 schema、单写和锁要求并非新增程序强制实现。真实 Orca 版本的 terminal surface/title/keep-open 组合仍需使用时验证。

## 后续

下游安装与更新方案另行设计；必要时使用授权的隔离样例实测三种模式，再决定是否增加确定性执行记录工具。
