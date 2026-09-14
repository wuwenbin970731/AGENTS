---
task_schema: 4
id: 2026-09-14-190000-progressive-task-runtime
title: Task 渐进式披露与项目初始化运行时
summary: "将 AGENTS 仓库升级为可初始化项目并以 taskctl 渐进管理跨会话任务的核心仓库"
status: "awaiting_user"
mode: rigorous
design_status: "implemented"
tags: [agents, task-system, taskctl, bootstrap]
checkpoint: "AGENTS Core 渐进式 Task Runtime、双目标 Review gate 与可直接复制 Prompt 已完成并通过提交前验证"
next_action: "基于推送后的干净 Core 提交生成系统级 dry-run，等待用户 Review 后再应用"
revision: 13
created_at: 2026-09-14T19:00:00+08:00
updated_at: "2026-09-14T21:26:23+08:00"
verified_at: "2026-09-14T21:26:23+08:00"
parent_task: null
depends_on: []
---

# Task 渐进式披露与项目初始化运行时

## 任务契约

- 目标：把本仓库从纯 Markdown 模板升级为个人 Agent 的核心初始化仓库，并以脚本保证 Task 渐进式披露、跨会话恢复、并发写入和系统级规则同步边界。
- 完成标准：新项目可安全初始化；Task 只按 Meta、入口、资源、证据逐级加载；多会话更新不会静默覆盖；系统级规则可保留本机扩展地安全更新；模板、Skill、CLI 和 README 一致；自动化测试通过。
- 范围：`.tasks/` schema 4、`taskctl`、`task-runtime` Skill、项目初始化脚本、系统级规则同步脚本、规则模板、文档和测试。
- 非目标：自动提交或推送；批量迁移其他项目中的旧 Task；自动更新已有下游项目；引入数据库或第三方 Python 运行依赖。

## 当前工作状态

- 当前正在解决：第一版实现和系统级规则同步补充均已完成，等待用户 Review。
- 已确认的关键事实：用户确认默认目录为 `.tasks/`；一个 Task 可对应多个会话；其他 Task 必须 Meta-first；当前实际生效的系统级规则位于 `~/.codex/AGENTS.md`，并包含必须保留的 `.TRAE` 本机扩展。
- 当前方案或决定：frontmatter 是 Meta 唯一权威来源；资源按 Context Map 显式点读；revision 防止静默覆盖；项目初始化和系统级规则同步分离；全局同步只替换带哈希的 Core 受管块。
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：用户提出 Review 意见、实现自动 `sync_project.py` 或修改同步协议。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| `design/CURRENT.md` | schema 4、加载状态机、运行时和迁移完整设计 | 修改协议、接口、并发行为或评审设计取舍时 |
| `iterations/F000-implementation.md` | 第一版 Task Runtime 实现和验证证据 | 核验初始实现命令或排查对应测试失败时 |
| `iterations/F001-global-agents-sync.md` | 系统级同步器、实际迁移和验证证据 | 核验全局规则更新、安全边界或迁移结果时 |
| `iterations/F002-combined-review-gate.md` | 系统级与项目级合并 Review、计划摘要和当前待确认项 | Review 更新流程或准备应用当前系统级计划时 |

## 依赖契约

- 依赖任务：无。
- 当前任务向其他任务提供：可安装的 `.tasks/` 运行时、项目级 Task Skill、项目初始化入口和系统级规则安全同步入口。
- 当前任务从其他任务消费：无。
