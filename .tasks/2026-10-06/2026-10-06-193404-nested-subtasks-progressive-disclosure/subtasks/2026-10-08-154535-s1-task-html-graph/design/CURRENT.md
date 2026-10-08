# Task HTML 关系图谱设计

## 目标

为任意父 Task 生成可重复刷新的单文件 HTML 关系图谱。图谱展示有界后代树、每个节点的稳定编号、状态、检查点和直接子节点数。

## 事实源与边界

- `TASK.md` frontmatter 仍是唯一事实源。
- 图谱只读取 `taskctl tree` 已使用的 L0 Meta，不读取 Task 正文或 Context Map 资源。
- HTML 是派生快照，不接受状态编辑，也不成为索引或缓存事实源。
- 深度复用 `MAX_TREE_DEPTH=8`，节点上限复用 `MAX_TREE_LIMIT=100`。
- 超出节点预算时显示 `remaining_count`，不静默扩展。

## CLI 契约

```bash
.tasks/bin/taskctl graph <task-id> \
  --depth 3 \
  --limit 100 \
  --output evidence/task-graph.html \
  --am-cli /path/to/am.mjs
```

- 默认深度为 3，默认节点上限为 100。
- 默认输出到所选 Task 的 `evidence/task-graph.html`。
- 相对 `--output` 从所选 Task 目录解析；拒绝越界路径、`subtasks/` 和非 HTML 后缀。
- `--am-cli` 可指向 `am` 可执行文件或 `am.mjs`。未指定时检查全局 `am`、`ANSWER_ME_WITH_HTML_CLI` 和常见 Skill 安装路径。
- 默认传给渲染器 `--no-open`；显式 `--open` 才打开页面。
- 命令输出生成路径、节点数、剩余节点数、深度和稳定数据指纹。

## 生成流程

1. 解析根 Task，只读取所有任务的 frontmatter。
2. 按 `parent_task` 和 `subtask_key` 建立有界树。
3. 从返回节点生成 answer-me-with-html 扩展 Markdown。
4. 将草稿通过标准输入传给渲染器，不拼接 Shell 命令。
5. 先渲染同目录临时文件，成功后原子替换目标 HTML。

## 页面内容

- 根 Task 概览：ID、状态、查询深度、节点预算和数据指纹。
- Task 树：稳定编号、标题、状态和直接子节点数。
- 状态汇总：只统计当前有界结果，并明确剩余节点数量。
- 未完成节点：显示状态与当前检查点，不推断完成度百分比。
- 披露边界：声明页面仅包含生成时的 L0 快照。

## 兼容与失败语义

- Schema 4 和 Schema 5 都通过现有虚拟树参与渲染。
- 未安装 `answer-me-with-html` 时，`graph` 返回可操作错误；现有 `tree --format json` 保持可用。
- 渲染失败时保留已有图谱，不留下部分写入。
- Task Runtime 不复制或绑定用户级 Skill，实现仅依赖 Python 标准库。

## 验收

- 真实的三级 Task 树可生成 HTML，页面不泄露 Task 正文标记。
- 深度和节点上限生效，页面显示剩余节点数。
- 路径越界、缺少渲染器和渲染失败均可预测地报错。
- 重复生成相同图谱可安全覆盖旧页面。
- 初始化后的下游项目包含该命令、文档和测试覆盖。
