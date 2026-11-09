# 环境级批量同步工作流

## 1. 配置和入口

每台实际执行机器/用户维护自己的 `~/.config/agents-core/repos.json`。命令可以通过 `--config <绝对路径>` 指定另一份清单；不使用 cwd 推断目标。配置示例见 config.example.json，所有路径在当前执行环境解释，只接受绝对路径或 `~`。

- `core_checkout`：已配置认证 origin 的可信 Core 检出；每轮 prepare 显式 fetch origin/main。
- `control_workspace`：独立共享控制目录，默认 `~/.local/share/agents-core/control`，不得嵌套在 Core 或目标项目中。
- `defaults.agent`：明确选择的 Agent。null 时 inspect 可用，prepare 前需要用户选择；用 --agent 本轮覆盖即可，不必改写配置。不推断模型/effort。`max_parallel` 默认为 3，范围 1–32。
- `repos`：稳定 id、path、enabled（默认 true）；默认全部 enabled。可重复 `--repo <id>` 选择子集；未登记/禁用/重复 ID 会拒绝。真实路径别名去重，目标不是仓库根或缺乏正式受管基线时独立报告阻塞，不自动克隆或初始化。
- `global_targets`：当前客户端实际使用的系统级文件，显式 id/path，真实路径去重。Codex 示例不是其他客户端的默认目标。旧全局文件需要迁移时可显式给出 `adopt_local_tail_from`，仍需具体内容 Review。

本地、SSH 独立发起两轮。SSH 下整个脚本、配置、Core fetch、控制状态、项目命令和 worker 都在远端；本地 Orca 客户端不得把远端 path 当本机 path 使用。发起前按 Orca 指南核对实际 workspace/host。配置和回执只存环境私有位置，不提交私人路径/凭据。

新下游可自动发现安装的 core-sync Skill。旧下游没有 Skill 时，用户可以给 Agent：

```text
请读取当前执行环境 ~/.config/agents-core/repos.json，
加载其中 core_checkout 指向的 skills/core-sync/SKILL.md，
先 inspect 并展示本轮目标；不要直接应用更新。
```

也可从任何 cwd 调用可信共享检出的 `python3 <core_checkout>/scripts/core_sync.py inspect`；该入口不要求当前项目安装新 Skill。配置、可信入口是显式引导，不自动扫描磁盘或切换未经确认的源仓库。

## 2. 一次性控制工作区准备

控制目录必须先存在，并按 Core README 的首次安装协议准备：对实际系统级目标运行 sync_global_agents.py dry-run，对控制目录运行 init_project.py dry-run；合并展示具体动作与摘要，用户 Review 后才应用获批部分。不要只因为是控制目录就省略系统级提案，或自动覆盖未知 .tasks。

工具 prepare 只接受已受管、Task schema 5 的控制工作区。它不会隐式修改当前项目、用户配置或安装全局 Skill。控制目录是运行控制空间，不是 Core 代码镜像；私有配置和批次状态不应发布到仓库。

## 3. inspect 和 prepare

```text
python3 <entry> inspect --config <registry.json>
python3 <entry> prepare --config <registry.json> [--repo project-a --repo project-b] [--agent codex] [--max-parallel 3]
```

prepare 读取清单、验证控制工作区、串行持有独立准备锁以防重复批次，刷新认证 origin/main 并固定完整 SHA。不回退历史缓存；认证/fetch/基线读取失败停止。它创建独立干净 Git 快照，以该正式提交的 README/COPY_MAP 作为本轮协议和源；本地 Core 中未提交修改不会作为 theirs。

origin/main 必须已经发布本功能（core-sync Skill 以及 task-orchestration/planctl）；否则明确停止，不从 dirty 工作树补缺失文件。因此开发完成不等于新功能已在远端可用，正式使用需先经用户批准发布 Core。

prepare 的写入仅限缓存/控制状态、控制工作区的 Task/Subtask 和 Core 检出的 fetch 引用，不写系统级/下游文件。状态位于 `<control>/.tasks/.state/core-sync/<batch-id>/`，返回的 batch 路径用于以后所有命令。源 Git 快照单独位于该批次的 source 子目录。源内容/HEAD/origin 后续改变或 config 漂移时停止。

创建的主 Task 包含中文执行树与 schema 2 策略的 Context Map。每目标一个稳定 Subtask。workspace 的 `registry:<id>` 是冻结配置定位引用，不是 Orca CLI selector；解析并核对当前环境 workspace 后才派发。blocked 项有显式未满足依赖，不启动 worker。

同一实际项目或共享系统级目标不得同时属于两个未关闭批次。准备过程 journal 记录已创建 Task；中断时按该 journal 和 Task Meta 恢复，不重复 prepare。残留 prepare.lock 须先核对旧协调进程再人工解除，不自动抢占。缺少正式 batch.json 的失败准备也可在确认无 worker 后 close 登记；不自动删除其证据或 Task。

## 4. 编排批准和 worker 生命周期

先展示 `render --batch <batch>` 及控制 Task 的 schema 2 计划供 Review。按 task-orchestration 保存具体版本/摘要/编排批准，用 planctl 校验和计算候选；本工具不伪造编排批准。主 Agent 按 max_parallel 限制活动 worker 数，依 Orca 消息与唤醒机制推进，不后台轮询。

worker 在配置中的目标仓库现有 workspace 内执行；控制 Subtask 入口位于共享控制工作区，Task 命令显式指定 `--root <control>`。目标仓库原有的 Task 不作为控制主 Task，不复制 Core 自用 Task。修改 Subtask 用 revision 检查。

brief 至少包含：batch ID、配置 repo ID、控制 Task ID、固定 SHA/源快照、目标 workspace、该快照 README 的更新协议、允许文件范围、不得写共享系统级文件、预览里程碑与最终完成条件、回报/提问方式。

预览完成时发里程碑/问题并等待协调者回复，不以 worker_done 宣告整个同步 Subtask 完成。所有 worker 已预览或明确阻塞后主 Agent汇总内容 Review。等待用户时结束协调回合，让 Orca 唤醒；不用终端输入轮询。后续优先回复原 worker；旧实例关闭时按恢复协议续跑同一 Subtask，先检查旧 attempt，不能凭沉默新建重复实例。

## 5. 并行项目预览

```text
python3 <entry> preview --batch <batch> --repo project-a
python3 <entry> preview --batch <batch> --repo project-a --proposal-file <semantic-proposal.md> --observe <relative-file>
```

项目 helper 按自身 manifest 的 source_commit 恢复旧 COPY_MAP 与基线文件，核对 manifest 的源哈希；新源来自固定快照。不解析任意配置命令，不执行旧版 Python 源，只静态解析 COPY_MAP。未来 COPY_MAP 变为不支持的表达式时明确停止，不能漏文件继续更新。

结果分类：无需变更、可更新/新增、保留本地修改、双方修改需语义合并、候选删除默认保留。这只是字节级预分类，worker 必须逐文件/章节检查并输出可审阅的具体补丁与语义说明。不得把 conflict 自动转为覆盖。旧文件和脚本的模式也纳入输入状态；新安装模式遵守固定版本初始化器，taskctl 保持可执行。

所有比较文件、manifest 和 AGENTS.override.md 自动记录输入快照；额外读取并影响判断的项目文件须用重复 `--observe` 登记。先核对项目实际 AGENTS/override、客户端规则与环境；只看 managed 文件不等于已完成语义检查。符号链接、非普通目标和无法重现的历史基线均阻塞。

用 --proposal-file 重新预览时将具体语义提案内容一并绑定到 Review。单有字节比较不算完整项目提案。worker 独占自身 preview 文件；主协调者不得在 worker 仍改提案时批准。

提案至少说明：直接更新/本地专属/双方一致/冲突/新增/候选删除/不变、具体补丁、保留内容、风险、文件模式、验证命令、是否只做部分更新、manifest 处理。不要在提案或 Task 中复制凭据及无关私有数据。

## 6. 共享系统级预览与合并 Review

```text
python3 <entry> preview-global --batch <batch> --target codex
python3 <entry> review --batch <batch>
python3 <entry> render-review --batch <batch>
```

只由协调者按去重后的实际目标执行。preview-global 调用固定源同步器 dry-run，并保留完整预期内容、原内容/预期内容指纹与 plan_digest；冲突独立记录，不覆盖。所有项目和系统目标有预览或明确阻塞后才能构成合并 Review。render-review 输出中文系统级内容与项目提案，摘要与 review 的 JSON 同源。

阻塞项目不阻止你批准其他已经预览的项目。每次具体批准都必须指向当前 review_digest；编排批准不等于内容批准，无冲突也不能省略此门。可只批准系统级、只批准项目或项目文件子集。

## 7. 批准与应用前 gate

用户 Review 后，协调者把明确选择写入私有 JSON（没有“全部未来更新”的授权）：

```json
{
  "projects": {"project-a": ["AGENTS.md", ".tasks/bin/taskctl"]},
  "globals": ["codex"]
}
```

```text
python3 <entry> approve --batch <batch> --review-digest <digest> --selection <selection.json> --basis <explicit-user-approval>
python3 <entry> gate-global --batch <batch> --target codex
```

工具绑定批准摘要和明确依据，保留批准历史；不能证明依据是否真实，Agent 不得自造批准。后一次 approve 是本轮最新的完整批准选集，不隐式累加；补充批准时重新列明完整范围。

系统级 gate 成功后，仅协调者用固定源 scripts/sync_global_agents.py 和返回的 sync_plan_digest，以及原来的 target/迁移边界执行 --apply --approve-plan。随后：

```text
python3 <entry> record-global --batch <batch> --target codex
python3 <entry> gate --batch <batch> --repo project-a
```

record-global 要求实际文件内容/模式与获批预期完全一致。项目 gate 要求所有获批系统级更新有正确结果记录；未获批系统级目标须保持预览时状态。仅批准项目且系统文件未改时可独立放行；若项目语义上依赖未获批系统变化，应额外阻塞，不能扩张用户授权。

项目 gate 返回 apply_allowed、approved_files、manifest_advance_allowed。gate 不写下游文件、也不强制约束之后的任意 shell 操作；worker 必须严格按获批文件语义合并，不整文件覆盖 AGENTS.md、不自动删除本地内容。不处理 gate 到真实写入之间的外部竞争，写入前还需核对工作区状态，并在目标有其他写入者时停止协同处理。

只批准部分文件、尚有必要变化未批准时 manifest_advance_allowed=false：保留旧 source_commit/files，不把未应用文件伪装成新基线。即使该标志为 true，也必须在全部合并和验证成功、项目契约满足后才更新 manifest；源文件哈希取固定源，实际保留的本地修改不等于源文件。不得把待同步内容写成已安装事实。候选删除默认保留，并单独报告。

## 8. 验证、部分完成与恢复

按固定 README 完成全局 unchanged、Task CLI 版本/doctor、全部相关 Skill 校验、diff check 与项目受影响测试，核对可执行位和最终 manifest。共享全局验证由协调者统一做，项目 worker 不重复写全局。提示新会话发现新规则/Skill。

项目实际执行后可使用 `record-project --batch <batch> --repo <id> --result-file <result.json>` 记录结果。result 包含 outcome（updated/unchanged/partial/failed/blocked）、证据入口 evidence，成功/部分完成还需 checks 列表（command 与实际 returncode）。命令文本仅作证据，不自动执行。工具检查获批范围外的已观察文件未变、完整成功时实际 manifest 符合新源及文件存在/入口模式、部分完成时基线未推进；仍不能证明检查确实执行或语义合并正确。

每 repo 的运行状态、attempt、真实 workspace/terminal/dispatch、输入摘要、批准、验证和错误记录在私有状态；Task 只作脱敏恢复索引。脚本不提供证据真实性或测试执行证明，最终报告只能引用实际观察。

配置/路径、固定源、目标文件（含模式）、附加观察文件或提案变化时，gate 拒绝旧批准。已经部分应用导致旧输入失效时，先保留 diff、确认旧 worker，再生成剩余内容预览并重新 Review；不回滚用户文件，不抹掉旧证据。配置已改或源损坏时不能用旧批次应用，需明确关闭后重新准备。

被拒绝/未批准/失败项目维持 awaiting_user 或 blocked，并明确标为未完成；不能为结束批次而标 completed。已完成项目独立核验。只有所有目标达成约定标准时才能完成批次目标；用户明确结束部分批次时如实记录未完成范围。

确认 worker 已结束或按 Orca 协议停止后，才可 `close --batch <batch> --basis <reason>` 解除批次占用。关闭记录不证明进程退出，也不自动更新 Task 状态、不删除目标/源/terminal、不提交推送。关闭后 gate 不再放行。未关闭批次阻止同一实际目标重复 prepare。
