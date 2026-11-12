---
task_schema: 5
id: "2026-11-11-213248-orca-codex-session-naming"
title: "Orca Codex 无打断会话命名"
summary: "验证真实 Orca/Codex 会话关联，并实现无打断命名、恢复保护及编排接入"
status: "completed"
mode: rigorous
design_status: "implemented"
tags: []
checkpoint: "无打断命名接入完成；98 项回归、Skill 校验、初始化预览与真实会话只读恢复验证通过"
next_action: "等待用户决定是否提交；SSH 与其他 Codex 版本按需独立验证"
revision: 12
created_at: 2026-11-11T21:32:48+08:00
updated_at: "2026-11-12T11:26:31+08:00"
verified_at: "2026-11-12T11:26:31+08:00"
parent_task: null
subtask_key: null
depends_on: []
---

# Orca Codex 无打断会话命名

## 任务契约

- 目标：验证真实 Orca/Codex 会话关联，并实现无打断命名、恢复保护及编排接入
- 完成标准：真实仿真验证准确 thread 绑定与显式命名；实现外部命名工具、编排接入和安装映射，通过回归并记录失败与未验证边界。
- 范围：本仓库命名辅助工具、编排 Skill、安装映射及相应测试。
- 非目标：不修改业务会话或全局配置，不提交、推送或更新下游。

## 当前工作状态

- 当前正在解决：命名工具、编排接入与恢复保护已完成，98 项回归及本机只读恢复验证通过。
- 已确认的关键事实：本机 Codex 0.167.0 支持元数据改名；真实 CLI 按新名称恢复到了同一会话。
- 当前方案或决定：采用 design/implementation.md 契约，主 Agent 身份核验后从外部尽早命名，失败不阻塞业务。
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：用户要求提交、扩展或验证其他执行环境时。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| evidence/implementation-validation.md | 工具接入、回归与只读恢复验证 | 复核本轮交付时 |
| design/implementation.md | 用户批准的命名接入契约 | 实现或恢复本轮优化时 |
| evidence/supervised-simulation.md | 真实 Subtask 仿真、外部 session 绑定及稳定性边界 | 评估无打断命名方案或生产化设计时 |
| evidence/result.md | 实测结果、边界和脱敏绑定证据 | 评估命名适配实现或复核验证时 |
| design/validation.md | 已授权的独立测试设计 | 执行命名接入验证时 |

## 依赖契约

- 依赖任务：无
- 当前任务向其他任务提供：会话命名接入的实测证据
- 当前任务从其他任务消费：无
