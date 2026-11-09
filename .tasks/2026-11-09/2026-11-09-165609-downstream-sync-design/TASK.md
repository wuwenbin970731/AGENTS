---
task_schema: 5
id: "2026-11-09-165609-downstream-sync-design"
title: "下游仓库批量同步"
summary: "设计共享仓库清单与跨项目入口，通过并行 Subtask 按 README 协议更新下游并汇总 Review"
status: completed
mode: rigorous
design_status: implemented
tags: []
checkpoint: "本轮实现与验证完成；用户已 Review 并批准提交信息，执行本地提交"
next_action: "按后续授权发布；各环境配置清单与控制工作区后进行真实实测"
revision: 7
created_at: 2026-11-09T16:56:09+08:00
updated_at: "2026-11-09T18:03:14+08:00"
verified_at: "2026-11-09T17:41:27+08:00"
parent_task: null
subtask_key: null
depends_on: []
---

# 下游仓库批量同步

## 任务契约

- 目标：设计共享仓库清单与跨项目入口，通过并行 Subtask 按 README 协议更新下游并汇总 Review
- 完成标准：共享配置、任意 cwd 入口、并行 Subtask、两阶段 Review 与漂移校验实现；隔离集成测试与仓库检查通过。
- 范围：本仓库代码、Skill、安装清单、文档与隔离测试。
- 非目标：不更新真实下游、不启动真实 worker、不提交或推送。

## 当前工作状态

- 当前正在解决：本地实现与隔离验证完成；未配置真实清单或更新真实下游。
- 已确认的关键事实：README 要求认证 fetch 固定 SHA、三方语义比较及系统级/项目级合并 Review。
- 当前方案或决定：每环境独立清单与批次；默认全部启用；集中处理系统级目标，项目并行预览和获批应用。
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：形成设计结论或完成首个已验证里程碑。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| evidence/validation.md | 本轮交付、73 项测试与实际执行边界 | 评估交付、提交或准备真实使用时 |
| design/implementation.md | 已批准方案的实现边界和验证计划 | 实现、验证或恢复开发时 |
| design/requirements.md | 需求、README 约束及待确认设计边界 | 需求 Review、设计批量同步方案时 |

## 依赖契约

- 依赖任务：无
- 当前任务向其他任务提供：core-sync Skill、共享入口、安装映射与验证记录
- 当前任务从其他任务消费：现有 Task Runtime 与编排能力
