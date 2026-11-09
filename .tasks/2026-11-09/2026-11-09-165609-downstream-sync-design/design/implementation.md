# 批量 Core 同步实现设计

用户已批准环境独立清单、共享入口、并行预览及获批应用方案。

## 实现范围

新增 core-sync Skill 和 Python 标准库辅助工具，配置只描述当前环境的路径与偏好。从任意 cwd 加载同一配置。inspect 只读；prepare 显式刷新 origin/main 并固定 SHA，在共享控制工作区的私有 .tasks/.state/core-sync 下创建干净源快照与批次记录，创建一个主 Task 和每 repo 一个 Subtask，输出中文执行树。

控制工作区必须先按现有 README 协议完成首次安装；工具不越过该 Review 门自动接管目录。源快照与控制状态分离，冻结目标真实路径、配置哈希、环境标识、source SHA 和 Task ID。源快照为独立干净 Git 克隆，拒绝本地 dirty 源作为同步基线。

新增 preview/preview-global、review、approve、gate 辅助步骤：项目预览比较固定 base/ours/theirs 并保存输入快照，Agent 补充语义提案；主 Agent 汇总系统级与项目级预览；批准绑定具体提案摘要和文件选集，应用前重查配置/目标/源/提案是否变化。脚本不自动写下游文件，合并仍由 worker 执行 README 协议。多项目 worker 写各自独立结果文件，批准由协调者单写。

各 repo 各自失败独立记录。系统级目标在配置中显式列出，规范化去重；由协调者统一 preview/apply，不交给项目 worker。预览期不改系统/项目目标。已批准的系统级变化成功后，记录真实 post-state；项目应用前核对该已批准结果，避免将合法更新误报为输入漂移。

COPY_MAP 加入 core-sync 和上一轮 task-orchestration 的全部必要源文件。项目路由与 README 添加按环境批量入口、旧下游引导和一次性配置说明。无第三方运行依赖，不自动提交或推送。

## 验证

使用临时本地 Git origin、Core 镜像、控制工作区和两个下游模拟 prepare、独立基线比较、合并 Review、部分批准、输入漂移和恢复门。检查安装映射完整、旧目标无变化与 Task 结构；运行全套测试、各 Skill 校验、doctor、diff check、初始化 dry-run。真实 SSH/Orca worker 不在本轮实测范围，明确交付边界。
