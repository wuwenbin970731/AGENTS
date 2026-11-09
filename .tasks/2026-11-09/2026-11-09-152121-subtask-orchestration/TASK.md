---
task_schema: 5
id: "2026-11-09-152121-subtask-orchestration"
title: "Subtask Orca 执行编排"
summary: "设计并实现独立 task-orchestration Skill，连接持久化 Subtask 与 Orca terminal、调度和验收"
status: "completed"
mode: rigorous
design_status: implemented
tags: []
checkpoint: "本轮 Task 已完成；用户已 Review 并批准提交信息，提交本轮实现与验证记录"
next_action: "本轮无剩余实现；真实 Orca 实测及下游安装更新另立任务"
revision: 9
created_at: 2026-11-09T15:21:21+08:00
updated_at: "2026-11-09T16:48:08+08:00"
verified_at: "2026-11-09T15:56:09+08:00"
parent_task: null
subtask_key: null
depends_on: []
---

# Subtask Orca 执行编排

## 任务契约

- 目标：设计并实现独立 task-orchestration Skill，连接持久化 Subtask 与 Orca terminal、调度和验收
- 完成标准：三种模式、后代选集、terminal 关联、逐层验收与恢复形成 Skill；本地工具和分层调度测试通过。
- 范围：本仓库 Skill 和路由；不更新下游或启动真实 worker。
- 非目标：不实现后台调度器、不变更 Task schema、不修改初始化器。

## 当前工作状态

- 当前正在解决：后代调度本地实现完成；真实 Orca 执行与下游部署未在本轮验证。
- 已确认的关键事实：Orca 当前指南提供 supervised worker、唤醒和 low-level terminal topology。
- 当前方案或决定：并列 Skill 复用 Orca；schema 2 工具校验层级/依赖并计算前沿，记录与真实执行仍由协调者维护。
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：形成设计结论或完成首个已验证里程碑。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|
| evidence/descendants-validation.md | 后代调度实际验证及证据边界 | 评估后代调度交付或准备实测时 |
| evidence/example-review.md | 中文多层执行树演示快照 | 需要查看可视化方案样例时 |
| design/descendants.md | 后代调度的结构化计划及阶段图设计 | 实现或验证后代编排时 |
| decisions/visual-review.md | 可视化 Review 要求及后代编排边界 | 设计多层编排或检查启动授权时 |
| evidence/validation.md | 检查结果及证据边界 | 评估验证范围或准备实测时 |
| design/orchestration.md | 已确认范围、职责和状态设计 | 修改编排设计或核对交付边界时 |

## 依赖契约

- 依赖任务：无
- 当前任务向其他任务提供：编排 Skill 首版
- 当前任务从其他任务消费：无
