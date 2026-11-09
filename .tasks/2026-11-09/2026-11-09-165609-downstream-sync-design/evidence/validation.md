# Core 批量同步交付与验证

## 交付

- core-sync Skill、配置模板、完整操作/恢复协议与独立 Python 标准库辅助工具。
- scripts/core_sync.py 共享入口：任意 cwd 读取同一环境清单；本地与 SSH 环境分别发起。
- inspect / prepare：目标检查，认证 Git fetch 接口、固定 origin/main SHA、独立干净快照、共享控制 Task/Subtask、中文执行树及可被 planctl 校验的策略。
- preview / preview-global / review / render-review：旧清单基线重现、文件/模式差异、语义提案绑定和共享系统级/项目级合并 Review。
- approve / gate / gate-global / record-global / record-project / close：具体批准范围、输入漂移校验、结果核对、部分更新基线保护和显式批次收尾；不代替实际语义合并与验证。
- COPY_MAP 完整登记 core-sync 5 项及 task-orchestration 7 项；更新 README 和项目路由。

## 最终执行检查

- python3 -m unittest discover -s tests -v：73 tests，201.400 秒，全部通过。
- 本轮新增 24 项 core-sync 测试；原有 49 项继续通过。
- 临时本地 Git origin、不同基线的下游、控制仓库模拟：固定新提交、旧工作树不混入、目标不被预览写入、只选择启用项、任意 cwd、独立失败、共享系统级竞争、部分批准、输入/模式/提案/配置漂移、源污染、重复批次、环境错配、历史基线错误、符号链接、成功结果与安装清单核对。
- 动态 COPY_MAP 扩展会拒绝，而非静默漏文件；畸形项目 manifest 独立阻塞，不隐藏健康目标。
- core-sync、task-orchestration、task-runtime 的 quick_validate 均通过。PyYAML 使用已有临时目录，不新增项目或全局运行依赖。
- taskctl doctor：5 tasks，0 errors，0 warnings。
- git diff --check：通过。
- 初始化器临时目标 dry-run：apply=false；core-sync 5 项、task-orchestration 7 项；总安装映射 25 项。未应用，目标 .tasks 不存在。
- 共享入口 --help 可用；源码通过编译检查。仅 taskctl 安装为可执行入口；新 Python 工具按文档通过 python3 调用，源/安装模式保持 0644。

## 证据边界与后续

- 测试中的系统级文件和下游仓库全部位于临时目录。没有修改真实用户配置、系统级文件或下游项目，没有启动真实 Orca worker，没有访问真实 SSH 目标，也没有证明真实网络认证成功。
- 本地文件 Git origin 验证了 fetch 失败不回退及固定提交语义；真实 GitHub/SSH 认证和 Orca 启动/回传仍需后续实测。
- helper 不自动覆盖下游、不自动做语义合并、不提供真实回执/测试真实性证明，也不强制约束之后任意 shell 行为；Agent 必须遵守 Review、文件范围及并发限制。
- 正式 prepare 要求 origin/main 已发布新功能。当前只是工作区实现，尚未提交、推送或发布；不可把本地 dirty 实现用作正式同步基线。
- 正式使用前每环境配置自己的清单与实际系统级目标，并按联合 dry-run Review 协议准备独立控制工作区。
