# 无打断命名接入验证

## 已实现

- 标准库 sessionctl：环境指纹、worker identity、协调者元数据命名与回读。
- 优先原生准确回执，其次正常初始化回传，已启用且完整的新鲜唯一索引仅作备用；多源矛盾不强行选择。
- 核对 thread、cwd 与首次 Task/Dispatch/随机 marker，禁止把 session 树根当实际 thread。
- 按会话加锁、原子私有记录、设置意图与回执丢失恢复、幂等核验、人工改名保护；命名不控制业务成败或验收。
- 中文执行方案包含会话名称；显式标题变化改变审阅摘要。安装映射、Core 同步计划与文档已接入。

## 实际验证

- 命名专项 24 项通过，编排专项 22 项通过。
- 三个 Skill 的 quick_validate 均通过。
- 初始化 dry-run：28 项动作，其中编排 Skill 9 个文件；apply=false，临时目标保持空目录。
- 本机已有独立 supervised 仿真会话：新工具使用初始化证据核验实际 name，返回 verified、changed=false。
- 同一会话移除外部证据再次执行：source=verified_record，仍为 verified、changed=false；未发送任何 TUI 输入或模型回合。
- 全量 unittest：98 项通过，耗时 185.406 秒。taskctl doctor：7 个 Task，0 错误、0 警告；git diff --check 通过。

## 边界

当前真实验证限本机 Codex 0.167.0 与此前独立仿真会话。新工具的真实调用均为已正确命名会话的只读核验；实际外部改名的真实证据见 supervised-simulation.md，新增设置与故障路径另由假服务自动化测试覆盖。本轮未另开 worker，未验证 SSH 或其他客户端版本，未声明跨环境稳定性。

接口无原子 compare-and-swap；设置前再次核对只能缩小竞争窗口。要求同环境共享命名 store、单协调协议；外部客户端同时改名仍存在竞争边界。

未提交、推送、更新下游或修改业务会话/全局配置；此前 README 的复制提示词编辑保留。
