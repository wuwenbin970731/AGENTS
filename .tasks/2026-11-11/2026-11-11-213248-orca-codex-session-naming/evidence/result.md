# Orca → Codex 会话命名实测

## 实测环境和范围

- 本机 Codex CLI 0.167.0；Orca 使用本次实际安装版本的指南和 help。
- 一个由 Orca agent launch --surface terminal 创建的专用测试会话；只要求回复 NAME_PROBE_READY，实际回复完成，未调用工具。
- 不修改业务任务、Codex 配置、生产编排代码；README 原有未提交改动保留。

## 验证结果

1. Orca 启动回执给 terminal handle 和 paneKey，没有 Codex session ID。
2. 对准确的测试 terminal 在空闲时输入 /status，屏幕返回准确 Session ID；未用“最新会话”或标题猜测。
3. 临时 App Server stdio 连接完成 initialize/initialized，通过 thread/read 确认测试标记和 ID。
4. thread/name/set 成功；thread/read 和 thread/list searchTerm 返回新名称，收到 thread/name/updated。
5. 原 TUI 仍持有 writer 时，第二 App Server 的 thread/resume 被明确拒绝：already has an active writer。未绕过保护。
6. 正常 /quit 释放原 TUI 后，用全新 App Server 按 ID resume 成功，返回同一 ID 和新名称。
7. 同一 Orca 测试 terminal 执行 codex resume <新名称>，真实 TUI 恢复；/status 同时确认同一 ID 与新名称。
8. 恢复启动遇到 Codex 更新菜单，仅按 Esc 跳过本次，没有升级或持久修改更新偏好。

## 行为边界

- 外部 API 改名后，原 TUI 退出提示仍用了缓存旧名称；新 TUI 恢复后显示持久化新名称。不能把旧 UI 缓存误判为改名失败。
- Orca worktree ps 的 pane 记录可提供 paneKey、类型与 conversationName，但这次没有 session ID。因此自动适配器需准确绑定来源（本次为该 terminal 的 /status），不能按创建时间碰运气。
- 本次验证的是普通 agent launch terminal。没有复现/修改 Orca supervised dispatch 的固定前导文案；不能据此声称前导污染的源码根因已修复。
- 生产方案可在取得准确 ID 后通过元数据接口改名，不必重新输入任务 prompt。已有运行中的 supervised worker 不应直接用 terminal send 强行插入 /status 或 /rename；应在派发前安全命名，或获取其受支持的真实会话绑定。
- 未验证 SSH 环境、其他 Codex 版本或 Orca Chat surface；未更改 session 数据库或 rollout 文件。
- 测试 terminal 已标记验证完成并正常退出 Codex；保存的测试会话保留，以便人工复核。没有删除会话。

## 脱敏证据

- 测试 session ID：`01a1cad0-c3d4-7633-b819-7914dce09196`
- 原名称：创建命名验证会话
- 新名称：命名验证 · S0 · Orca元数据接口
- 新连接按 ID 恢复：True
- 真实 CLI 按名称恢复且 ID 一致：True

私有原始回执与临时客户端保留在当前机器临时目录，不把 workspace 私人路径、认证信息或其他会话内容写入 Task。

参考官方文档：https://learn.chatgpt.com/docs/app-server 与 https://learn.chatgpt.com/docs/developer-commands?surface=cli。
