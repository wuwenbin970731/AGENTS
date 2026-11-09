#!/usr/bin/env python3
"""校验后代编排计划，生成中文执行树，计算调度前沿；不启动 Agent。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

MODES = {"manual-sequential": "验收串行", "auto-sequential": "自动串行", "parallel": "并行"}
PHASES = {"pending", "launching", "running", "reported", "failed", "unknown"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value, label):
    require(isinstance(value, list) and all(isinstance(x, str) and x for x in value), f"{label} 必须为字符串列表")
    require(len(value) == len(set(value)), f"{label} 含重复项")
    return value


class Plan:
    def __init__(self, data):
        require(isinstance(data, dict) and data.get("schema") == 2, "只支持编排计划 schema 2")
        self.data = data
        require(isinstance(data.get("plan_version"), int) and data["plan_version"] > 0, "缺少 plan_version")
        rows = data.get("nodes")
        require(isinstance(rows, list) and 1 < len(rows) <= 1000, "计划须包含根与后代，最多 1000 节点")
        self.nodes = {}
        for row in rows:
            require(isinstance(row, dict) and isinstance(row.get("task_id"), str) and row["task_id"], "缺少 Task ID")
            key = row["task_id"]
            require(key not in self.nodes, f"重复 Task ID：{key}")
            self.nodes[key] = row
            require(isinstance(row.get("title"), str) and row["title"].strip(), f"{key} 缺少标题")
            strings(row.get("children"), f"{key}.children")
            strings(row.get("known_children"), f"{key}.known_children")
            strings(row.get("depends_on", []), f"{key}.depends_on")
            require(set(row["children"]) <= set(row["known_children"]), f"{key} 选集不属于已知直接子节点")
            require(row["children"] or not row["known_children"], f"{key} 存在未展开后代，不得伪装成执行叶子")
            require(isinstance(row.get("completion_criteria"), list) and row["completion_criteria"]
                    and all(isinstance(x, str) and x.strip() for x in row["completion_criteria"]), f"{key} 缺少验收条件列表")
            if not row["children"]:
                require(all(isinstance(row.get(x), str) and row[x].strip() for x in ("agent", "terminal_title", "workspace")), f"{key} 缺少 Agent、终端名称或工作区")
        self.root = data.get("root_task")
        require(self.root in self.nodes, "找不到根 Task")
        self.parent, self.order, self.mode, self.complete = {}, [], {}, {}

        def visit(key, inherited, depth):
            require(depth <= 64, "层级超过 64，拆分为有界批次")
            require(key in self.nodes, f"选中节点不存在：{key}")
            require(key not in self.order, f"重复挂载或层级环：{key}")
            self.order.append(key)
            node = self.nodes[key]
            mode = node.get("mode", inherited)
            require(mode in MODES, f"{key} 调度模式无效")
            self.mode[key] = mode
            for child in node["children"]:
                self.parent[child] = key
                visit(child, mode, depth + 1)
            self.complete[key] = set(node["children"]) == set(node["known_children"]) and all(self.complete[c] for c in node["children"])

        visit(self.root, "manual-sequential", 0)
        require(len(self.order) == len(self.nodes), "存在未连到根的节点")
        external = data.get("external_dependencies", {})
        require(isinstance(external, dict) and not set(external) & set(self.nodes), "外部依赖不得覆盖选中节点")
        self.external = external
        for key in self.order:
            actor = self.nodes[key].get("acceptance_actor")
            require(actor in {None, "user", "coordinator"}, f"{key} 验收者配置无效")
            manual = key == self.root or self.mode[self.parent[key]] == "manual-sequential"
            require(not manual or actor != "coordinator", f"{key} 不得绕过上层人工验收")
        for key, value in external.items():
            require(isinstance(value, dict) and isinstance(value.get("completed"), bool), f"{key} 外部依赖缺少 completed")
            if value["completed"]:
                require(isinstance(value.get("basis"), str) and value["basis"].strip(), f"{key} 缺少外部依赖核对依据")
        self.edges = {}
        for key in self.order:
            start, finish = (key, "enter"), (key, "accept")
            self.edges.setdefault(start, set())
            self.edges[finish] = {start, *((c, "accept") for c in self.nodes[key]["children"])}
            if key in self.parent:
                parent = self.parent[key]
                self.edges[start].add((parent, "enter"))
                siblings = self.nodes[parent]["children"]
                index = siblings.index(key)
                if index and self.mode[parent] != "parallel":
                    self.edges[start].add((siblings[index - 1], "accept"))
            for dep in self.nodes[key].get("depends_on", []):
                require(dep in self.nodes or dep in external, f"{key} 依赖未解析：{dep}")
                if dep in self.nodes:
                    require(self.complete[dep], f"{key} 依赖部分覆盖节点 {dep}，不能代表完整 Task 交付")
                    self.edges[start].add((dep, "accept"))
        # Kahn's algorithm includes hierarchy, serial order and explicit dependencies.
        pending = {k: set(v) for k, v in self.edges.items()}
        while pending:
            free = {k for k, v in pending.items() if not v}
            require(free, "层级、顺序与依赖组合后存在环或死锁")
            pending = {k: v - free for k, v in pending.items() if k not in free}
        strategy = {k: v for k, v in data.items() if k not in {"review", "authorization", "revision", "runtime"}}
        self.digest = hashlib.sha256(json.dumps(strategy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def actor(self, key):
        if key == self.root or self.mode[self.parent[key]] == "manual-sequential":
            return "user"
        return self.nodes[key].get("acceptance_actor") or "coordinator"

    def frontier(self, runtime):
        require(isinstance(runtime, dict) and runtime.get("plan_digest") == self.digest, "执行状态与计划摘要不匹配")
        states = runtime.get("nodes", {})
        require(isinstance(states, dict) and set(states) <= set(self.nodes), "执行状态包含未知节点")
        require(isinstance(self.data.get("review", {}), dict) and isinstance(self.data.get("authorization", {}), dict), "Review 或授权记录无效")
        accepted = set()
        for key, state in states.items():
            require(isinstance(state, dict) and state.get("phase", "pending") in PHASES, f"{key} 执行阶段无效")
            acceptance = state.get("acceptance", {})
            require(isinstance(acceptance, dict) and acceptance.get("status", "pending") in {"pending", "accepted", "rejected"}, f"{key} 验收状态无效")
            if state.get("phase") == "reported":
                require(state.get("outcome") in {"succeeded", "failed"}, f"{key} 回报缺少结果")
            if acceptance.get("status") == "accepted":
                require(state.get("phase") == "reported" and state.get("outcome") == "succeeded", f"{key} 未成功回报却被验收通过")
                require(acceptance.get("actor") == self.actor(key) and isinstance(acceptance.get("basis"), str) and acceptance["basis"].strip(), f"{key} 验收者或验收依据不符合策略")
                require(isinstance(state.get("evidence"), list) and state["evidence"] and all(isinstance(x, str) and x.strip() for x in state["evidence"]), f"{key} 缺少验收证据")
                accepted.add(key)
        done = {(k, "accept") for k in accepted}
        entered = set()
        # Enter aggregate nodes virtually; leaf nodes only enter after dependency gates.
        for _ in range(len(self.nodes) + 1):
            before = len(entered)
            for key in self.order:
                deps = self.nodes[key].get("depends_on", [])
                external_ok = all(self.external[d]["completed"] for d in deps if d in self.external)
                if external_ok and self.edges[(key, "enter")] <= done:
                    entered.add(key)
                    done.add((key, "enter"))
            if before == len(entered):
                break
        for key in accepted:
            require(key in entered and all(c in accepted for c in self.nodes[key]["children"]), f"{key} 验收越过上游门或子节点尚未验收")
        for key, state in states.items():
            if state.get("phase", "pending") != "pending":
                require(key in entered, f"{key} 执行记录越过调度门")
                if self.nodes[key]["children"]:
                    require(all(c in accepted for c in self.nodes[key]["children"]), f"{key} 子节点未验收便回报汇总")
        result = {"plan_digest": self.digest, "launch": [], "aggregate": [], "accept": [], "blocked": [], "batch_complete": self.root in accepted}
        review, auth = self.data.get("review", {}), self.data.get("authorization", {})
        approved = (review.get("status") == "approved" and review.get("plan_digest") == self.digest
                    and review.get("plan_version") == self.data["plan_version"] and review.get("basis") and review.get("artifact"))
        if not approved or auth.get("state") != "authorized" or not auth.get("basis"):
            result["blocked"].append({"task_id": self.root, "reason": "方案待审阅、批准版本不符或尚未授权执行"})
            return result
        for key in self.order:
            if key in accepted:
                continue
            state = states.get(key, {})
            phase = state.get("phase", "pending")
            rejected = state.get("acceptance", {}).get("status") == "rejected"
            if key not in entered:
                result["blocked"].append({"task_id": key, "reason": "等待上层分支、前项验收或显式依赖"})
            elif rejected or phase in {"failed", "unknown"} or state.get("outcome") == "failed":
                result["blocked"].append({"task_id": key, "reason": "失败、状态不明或验收未通过，须先恢复"})
            elif phase in {"launching", "running"}:
                result["blocked"].append({"task_id": key, "reason": "执行中，不重复启动"})
            elif phase == "reported":
                if not state.get("evidence"):
                    result["blocked"].append({"task_id": key, "reason": "成功回报缺少证据，先补充交付证据"})
                else:
                    result["accept"].append({"task_id": key, "actor": self.actor(key), "task_completion_allowed": self.complete[key]})
            elif self.nodes[key]["children"]:
                if all(c in accepted for c in self.nodes[key]["children"]):
                    result["aggregate"].append({"task_id": key, "task_completion_allowed": self.complete[key]})
            else:
                result["launch"].append(key)
        return result

    def render(self):
        def clean(value):
            return str(value).replace("\n", " ").replace("\r", " ").replace("|", "／").replace("`", "'")
        lines = ["# 编排执行方案（待核对审阅记录）", "", f"方案版本：{self.data['plan_version']}", f"策略摘要：`{self.digest}`", "", "```text"]

        def walk(key, prefix="", connector=""):
            node = self.nodes[key]
            role = "协调汇总" if node["children"] else "执行；创建终端"
            mode = MODES[self.mode[key]] + ("；显式配置" if "mode" in node else "；默认或继承")
            gate = "用户验收" if self.actor(key) == "user" else "协调者检查"
            coverage = "完整覆盖" if self.complete[key] else "部分覆盖；不代表整个 Task 完成"
            policy = f"；{mode}" if node["children"] else ""
            lines.append(f"{prefix}{connector}{clean(node.get('subtask_key') or key)} {clean(node['title'])} [{role}{policy}；{gate}；{coverage}]")
            children = node["children"]
            next_prefix = prefix + ("    " if connector == "└── " else "│   " if connector else "")
            for i, child in enumerate(children):
                walk(child, next_prefix, "└── " if i == len(children) - 1 else "├── ")
            omitted = set(node["known_children"]) - set(children)
            if omitted:
                lines.append(next_prefix + "    未选中：" + "、".join(clean(x) for x in sorted(omitted)))

        walk(self.root)
        lines += ["```", "", "| 节点 | 依赖 | Agent / 终端 / 工作区 | 验收条件 |", "|---|---|---|---|"]
        for key in self.order:
            n = self.nodes[key]
            launch = "主 Agent 协调，不创建终端" if n["children"] else "；".join(f"{label}：{n.get(k) or '未指定'}" for k, label in (("agent", "Agent"), ("terminal_title", "终端"), ("workspace", "工作区"), ("model", "模型"), ("effort", "推理强度")))
            lines.append("| " + " | ".join(clean(x) for x in (key, "、".join(n.get("depends_on", [])) or "无", launch, "；".join(n["completion_criteria"]))) + " |")
        if self.external:
            lines += ["", "外部依赖（启动前重新核对）："]
            lines += [f"- {clean(k)}：{'已完成' if v['completed'] else '未完成，阻塞依赖方'}；{clean(v.get('basis', '待核对'))}" for k, v in self.external.items()]
        lines += ["", "验收串行：同层前项验收后进入下一分支；自动串行：证据检查通过后推进；并行：满足依赖的分支同时进入。", "父节点须汇总检查后再经上层验收；方案批准不等于结果验收。实际启动前仍须核对编辑冲突、实时状态与批准摘要。"]
        return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "render", "ready"))
    parser.add_argument("plan", type=Path)
    parser.add_argument("--state", type=Path, help="ready 必须提供，首次执行也需显式空 nodes 状态")
    args = parser.parse_args()
    try:
        plan = Plan(json.loads(args.plan.read_text()))
        if args.command == "render":
            print(plan.render(), end="")
        elif args.command == "ready":
            require(args.state is not None, "ready 需要 --state；恢复时不得用空状态替代旧记录")
            print(json.dumps(plan.frontier(json.loads(args.state.read_text())), ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"结果": "计划结构与组合依赖校验通过", "plan_digest": plan.digest, "节点数": len(plan.nodes)}, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({"错误": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
