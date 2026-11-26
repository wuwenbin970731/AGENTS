---
task_schema: 5
id: "2026-11-25-221916-task-shared-context"
title: "Task CONTEXT.md 共享上下文管理工作流"
summary: "为 Task 引入按需创建的 CONTEXT.md，支持祖先链共享、局部例外、预算加载及变更一致性检查。"
status: "completed"
mode: rigorous
design_status: "implemented"
tags: ["task-runtime", "context"]
checkpoint: "共享上下文工作流已实现并验收：全仓库125项、最终Runtime34项测试通过，配套检查通过"
next_action: "无；下游项目同步需另行安排"
revision: 10
created_at: 2026-11-25T22:19:16+08:00
updated_at: "2026-11-26T11:24:16+08:00"
verified_at: "2026-11-25T22:30:13+08:00"
parent_task: null
subtask_key: null
depends_on: []
---

# Task CONTEXT.md 共享上下文管理工作流

## 任务契约

- 目标：为 Task 提供按需创建的 CONTEXT.md，保存稳定约定，并使后代任务一致理解和使用。
- 完成标准：祖先链加载、显式局部例外、变更感知、预算与并发边界、旧任务兼容均通过场景验证；详细标准见 Context Map。
- 范围：Task Runtime Skill、协议、模板说明、taskctl、必要测试及本仓库自用副本。
- 非目标：不批量生成空文件、不自动归纳历史约定、不更新下游项目、不启动子代理。

## 当前工作状态

- 当前正在解决：实现和验证已完成；用户现已明确授权提交并推送本 Task 相关改动。
- 已确认的关键事实：改动前的协议仅加载所选入口；本次通过受限共享命令补齐祖先 CONTEXT.md 加载机制。
- 当前方案或决定：已实现 shared-list/read/check/write；按需创建、祖先链共享、显式局部例外、预算读取、内容指纹及 revision/短时锁保护。CLI 保留来源，语义冲突由 Agent 显式解决。
- 阻塞与解除条件：无技术阻塞。无；验收标准已满足。
- 下一次更新 Task 的触发点：出现回归、约定变更或用户要求重开。

## 共享约定

- 本地 CONTEXT.md 已保存已确认术语与范围；通过共享入口加载，恢复、执行和验收前检查指纹。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| `evidence/VALIDATION.md` | 实际验证结果、验收场景及限制 | 核查完成结论、排查回归或评估验证边界时 |
| `design/CURRENT.md` | 用户确认的需求、工作流方案、验收场景与实现待落实事项 | 启动实现、形成详细设计、检查范围或进行验收时 |

## 依赖契约

- 依赖任务：无。
- 当前任务向其他任务提供：已实现并验证的 Task 共享上下文管理能力；下游安装或更新仍需独立执行。
- 当前任务从其他任务消费：无。
