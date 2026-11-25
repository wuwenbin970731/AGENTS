#!/usr/bin/env python3
"""按环境准备 Core 批量同步、生成预览并校验具体批准；不覆盖下游文件。"""
from __future__ import annotations

import argparse
import ast
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import socket
import stat
import subprocess
import sys
import tempfile
import uuid

MARKER = "wuwenbin970731/AGENTS"
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".core-sync-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextlib.contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("批次记录正在写入；恢复前确认原协调者状态，不自动抢占锁") from error
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def run(command, *, binary=False):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=not binary)
    need(result.returncode == 0, f"{command[0]} 执行失败（退出码 {result.returncode}）；停止，不回退缓存")
    return result.stdout if binary else result.stdout.strip()


def git(path, *args, binary=False):
    return run(["git", "-C", path, *args], binary=binary)


def absolute(value):
    need(isinstance(value, str) and value, "路径必须为绝对路径或以 ~ 开头")
    path = Path(value).expanduser()
    need(path.is_absolute(), "不接受相对路径，避免受发起仓库 cwd 影响")
    return path.resolve()


def safe(root, relative):
    p = Path(relative)
    need(not p.is_absolute() and p.parts and ".." not in p.parts and ".git" not in p.parts, "不安全的项目相对路径")
    current = Path(root)
    for index, part in enumerate(p.parts):
        current /= part
        need(not current.is_symlink(), f"拒绝符号链接目标：{relative}")
        if index < len(p.parts) - 1 and current.exists():
            need(current.is_dir(), f"路径父级不是目录：{relative}")
    return current


def state(path):
    path = Path(path)
    need(not path.is_symlink(), "拒绝符号链接文件")
    if not path.exists():
        return {"kind": "missing"}
    need(path.is_file(), "目标不是普通文件")
    return {"kind": "file", "sha256": sha(path.read_bytes()), "mode": stat.S_IMODE(path.stat().st_mode)}


def environment():
    return digest([socket.gethostname(), str(Path.home().resolve()), os.getuid()])


def source_id(value):
    if value.startswith("/") or value.startswith("file://"):
        return str(Path(value.removeprefix("file://")).resolve())
    value = value.removesuffix(".git").rstrip("/")
    value = re.sub(r"^(https?://|ssh://)(git@)?", "", value)
    value = re.sub(r"^git@([^:]+):", r"\1/", value)
    return value


class Config:
    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()
        self.raw = load(self.path)
        need(isinstance(self.raw, dict) and self.raw.get("schema") == 1, "配置只支持 schema 1 对象")
        self.core = absolute(self.raw.get("core_checkout"))
        self.control = absolute(self.raw.get("control_workspace", str(Path.home() / ".local/share/agents-core/control")))
        need(not self.core.is_relative_to(self.control) and not self.control.is_relative_to(self.core), "控制工作区必须与 Core 源检出分离")
        defaults = self.raw.get("defaults", {})
        need(isinstance(defaults, dict), "defaults 必须为对象")
        self.agent = defaults.get("agent")
        need(self.agent is None or isinstance(self.agent, str) and self.agent.strip(), "Agent 配置无效")
        self.parallel = defaults.get("max_parallel", 3)
        need(type(self.parallel) is int and 1 <= self.parallel <= 32, "max_parallel 须为 1 至 32")
        self.repos, paths = {}, set()
        rows = self.raw.get("repos")
        need(isinstance(rows, list) and rows, "repos 不能为空")
        for row in rows:
            need(isinstance(row, dict) and ID.fullmatch(row.get("id", "")), "repo id 无效")
            key, path = row["id"], absolute(row.get("path"))
            need(key not in self.repos and path not in paths, "重复 repo id 或真实路径（包括符号链接别名）")
            need(not path.is_relative_to(self.core) and not self.core.is_relative_to(path)
                 and not path.is_relative_to(self.control) and not self.control.is_relative_to(path), "目标不得与 Core 或控制工作区重叠")
            need(type(row.get("enabled", True)) is bool, "enabled 必须为布尔值")
            self.repos[key] = {"id": key, "path": str(path), "enabled": row.get("enabled", True)}
            paths.add(path)
        self.globals, paths = {}, set()
        for row in self.raw.get("global_targets", []):
            need(isinstance(row, dict) and ID.fullmatch(row.get("id", "")), "系统级目标 id 无效")
            key, path = row["id"], absolute(row.get("path"))
            need(key not in self.globals and path not in paths, "重复系统级目标")
            need(not path.is_relative_to(self.core) and not path.is_relative_to(self.control)
                 and not any(path.is_relative_to(Path(r["path"])) for r in self.repos.values()), "系统级文件不得落在项目/Core/控制工作区中")
            self.globals[key] = {"id": key, "path": str(path), "adopt_local_tail_from": row.get("adopt_local_tail_from")}
            paths.add(path)
        self.fingerprint = digest({"raw": self.raw, "core": str(self.core), "control": str(self.control), "repos": self.repos, "globals": self.globals})

    def select(self, selected=None):
        keys = selected if selected else [k for k, r in self.repos.items() if r["enabled"]]
        need(keys and len(keys) == len(set(keys)), "选集为空或重复")
        need(all(k in self.repos and self.repos[k]["enabled"] for k in keys), "选集含未登记或禁用目标")
        return [self.repos[k] for k in keys]


def installed(repo):
    root = Path(repo["path"])
    need(root.is_dir(), "目标目录不存在")
    need(Path(git(root, "rev-parse", "--show-toplevel")).resolve() == root, "目标不是 Git 仓库根目录")
    config = load(safe(root, ".tasks/config.json"))
    need(isinstance(config, dict) and config.get("managed_by") == MARKER, "目标不是受管项目；不自动首次初始化")
    manifest = load(safe(root, ".tasks/agent-core.json"))
    need(isinstance(manifest, dict) and manifest.get("schema") == 1 and manifest.get("source_dirty") is False, "安装清单无可复现基线")
    need(isinstance(manifest.get("source"), str) and isinstance(manifest.get("source_commit"), str) and re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]), "清单缺少正式 source/source_commit")
    need(isinstance(manifest.get("files"), dict), "清单 files 无效")
    for path, value in manifest["files"].items():
        safe(root, path)
        need(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "清单文件哈希无效")
    return manifest


def inspect(config, selected=None):
    result = []
    for repo in config.select(selected):
        try:
            manifest = installed(repo)
            result.append({"id": repo["id"], "status": "ready", "source_commit": manifest["source_commit"]})
        except (ValueError, OSError) as error:
            result.append({"id": repo["id"], "status": "blocked", "reason": str(error)})
    return {"environment": environment(), "repos": result, "max_parallel": config.parallel,
            "control_ready": (config.control / ".tasks/config.json").is_file(), "global_targets": list(config.globals)}


def copy_map(source, revision=None):
    text = git(source, "show", f"{revision}:scripts/init_project.py") if revision else (source / "scripts/init_project.py").read_text()
    tree = ast.parse(text)
    assignment = next((n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COPY_MAP" for t in n.targets)), None)
    need(assignment is not None and isinstance(assignment.value, ast.List), "无法解析固定版本 COPY_MAP，需人工检查")
    for node in tree.body:
        if node is assignment or isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
            continue
        need(isinstance(node, ast.Assign), "COPY_MAP 所在模块含动态顶层行为，需人工检查映射")
        need(not any(isinstance(n, ast.Name) and n.id == "COPY_MAP" for n in ast.walk(node)), "COPY_MAP 存在动态赋值或别名，停止以免漏文件")

    def path_expr(node):
        if isinstance(node, ast.Name) and node.id == "SOURCE_ROOT":
            return Path()
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return Path(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return path_expr(node.left) / path_expr(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path" and len(node.args) == 1:
            return path_expr(node.args[0])
        raise ValueError("COPY_MAP 含不支持的表达式；停止而不猜测映射")

    result = {}
    for item in assignment.value.elts:
        need(isinstance(item, ast.Tuple) and len(item.elts) == 2, "COPY_MAP 格式无效")
        src, dest = map(path_expr, item.elts)
        safe(source, str(src))
        safe(source, str(dest))
        need(str(dest) not in result, "COPY_MAP 目标重复")
        result[str(dest)] = str(src)
    return result


def task(source, control, *args):
    return json.loads(run([sys.executable, source / "skills/task-runtime/scripts/taskctl.py", "--root", control, *args]))


def fill_task(source, control, folder, meta, body):
    entry = run([sys.executable, source / "skills/task-runtime/scripts/taskctl.py", "--root", control, "show", meta["id"], "--entry"])
    end = entry.index("\n---\n", 4) + 5
    temporary = folder / (meta["id"] + ".md")
    header = entry[:end]
    header = re.sub(r"(?m)^checkpoint:.*$", 'checkpoint: "批次准备完成，等待编排或内容 Review"', header)
    header = re.sub(r"(?m)^next_action:.*$", 'next_action: "核对真实 workspace 与批准，先预览后获批应用"', header)
    if meta["mode"] == "rigorous":
        header = re.sub(r"(?m)^status:.*$", "status: awaiting_user", header)
        header = re.sub(r"(?m)^design_status:.*$", "design_status: awaiting_user", header)
    temporary.write_text(header + "\n" + body, encoding="utf-8")
    try:
        return task(source, control, "write", meta["id"], "--from", str(temporary), "--expect-revision", str(meta["revision"]))
    finally:
        temporary.unlink(missing_ok=True)


def prepare(config, selected=None, agent=None, max_parallel=None, surface="same", current_surface=None,
            current_source="user_declared"):
    control_config = load(safe(config.control, ".tasks/config.json"))
    need(control_config.get("managed_by") == MARKER and control_config.get("task_schema") == 5,
         "请先按 README 完成控制工作区的首次安装 Review")
    need(config.globals, "先显式配置当前客户端实际使用的系统级目标")
    agent = agent or config.agent
    parallel = config.parallel if max_parallel is None else max_parallel
    need(isinstance(agent, str) and agent.strip(), "先配置或用 --agent 明确本轮 Agent，不推断当前模型")
    need(type(parallel) is int and 1 <= parallel <= 32, "本轮 max_parallel 须为 1 至 32")
    need(surface in {"same", "terminal", "chat"} and current_surface in {None, "terminal", "chat"}, "载体选择无效")
    need(current_source in {"runtime_verified", "user_declared"}, "当前会话来源无效")
    need(surface != "same" or current_surface is not None, "请提供已核实的 --current-surface 或显式 --surface；不从环境变量名猜测当前载体")
    resolved_surface = current_surface if surface == "same" else surface
    report = inspect(config, selected)
    need(any(r["status"] == "ready" for r in report["repos"]), "没有可预览目标")
    store = safe(config.control, ".tasks/.state/core-sync")
    with lock(store / "prepare.lock"):
        for old in store.glob("*/preparation.json"):
            previous = load(old)
            if ({r["path"] for r in previous["repos"].values()} & {r["path"] for r in config.select(selected)}
                    or {r["path"] for r in previous.get("globals", {}).values()} & {r["path"] for r in config.globals.values()}):
                need((old.parent / "closed.json").is_file(), "存在目标重叠的未关闭批次；请恢复旧批次，不重复启动")
        git(config.core, "fetch", "origin", "+refs/heads/main:refs/remotes/origin/main")
        commit = git(config.core, "rev-parse", "refs/remotes/origin/main^{commit}")
        origin = git(config.core, "remote", "get-url", "origin")
        need(not re.search(r"https?://[^/]*@", origin), "源 URL 不得内嵌凭据")
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:10]
        folder, source = store / batch_id, store / batch_id / "source"
        folder.mkdir(parents=True, mode=0o700)
        journal = {"environment": environment(), "repos": {r["id"]: r for r in config.select(selected)}, "created_tasks": [], "globals": config.globals}
        write(folder / "preparation.json", journal)
        run(["git", "clone", "--no-checkout", "--no-hardlinks", config.core, source])
        git(source, "fetch", str(config.core), commit)
        git(source, "checkout", "--detach", commit)
        git(source, "remote", "set-url", "origin", origin)
        need(load(source / ".tasks/config.json").get("managed_by") == MARKER, "刷新后的源不是 AGENTS Core")
        copy_map(source)
        need((source / "skills/core-sync/SKILL.md").is_file() and (source / "skills/task-orchestration/scripts/planctl.py").is_file(),
             "origin/main 尚未发布批量同步能力，先发布已验证版本；不使用 dirty 工作树替代")
        plan_tools = runpy.run_path(str(source / "skills/task-orchestration/scripts/planctl.py"))
        need(callable(plan_tools.get("resolve")), "origin/main 尚未发布双模式编排 schema 3；不使用 dirty 工作树替代")
        readme = (source / "README.md").read_text()
        heading = "### Core 更新后同步已有项目"
        need(heading in readme, "固定版本缺少 README 更新协议")
        protocol = readme.split(heading, 1)[1].split("\n### ", 1)[0].strip()
        (folder / "protocol.md").write_text(protocol, encoding="utf-8")
        parent = task(source, config.control, "new", "Core 批量同步 " + batch_id, "--slug", "core-sync-" + batch_id.lower(), "--summary", "按固定 Core SHA 并行预览，合并 Review 后仅应用获批变化", "--mode", "rigorous")
        journal["created_tasks"].append(parent["id"])
        write(folder / "preparation.json", journal)
        batch = {"schema": 1, "id": batch_id, "environment": environment(), "config_path": str(config.path), "config_digest": config.fingerprint,
                 "source_commit": commit, "source_origin": origin, "source": str(source), "control": str(config.control), "task": parent,
                 "agent": agent, "surface": resolved_surface, "surface_policy": surface,
                 "current_surface": current_surface, "max_parallel": parallel, "globals": config.globals, "repos": {}}
        for row in report["repos"]:
            child = task(source, config.control, "new", "同步 " + row["id"], "--slug", "sync-" + row["id"], "--parent", parent["id"], "--summary", "预览与合并 Review 后同步该项目，保留本地专属内容并验证", "--status", "pending")
            journal["created_tasks"].append(child["id"])
            write(folder / "preparation.json", journal)
            child = fill_task(source, config.control, folder, child,
                              f"# 同步 {row['id']}\n\n## 任务契约\n\n- 目标：按本轮固定 Core 提交更新配置目标 {row['id']}。\n- 完成标准：系统级/项目级合并 Review 后，仅应用获批文件；验证并记录保留、拒绝和未完成项。\n- 范围：目标由环境私有配置定位；不修改共享系统级文件，不自动提交或推送。\n\n## 当前工作状态\n\n- 状态：待编排批准，先预览，不写目标。\n- 固定 Core：{commit}。\n- 主 Task：{parent['id']}；批次：{batch_id}。\n- 按固定 Core README 更新协议执行；实际回执和路径只放环境私有状态。\n\n## 按需上下文地图\n\n| 资源 | 保存内容 | 读取条件 |\n|---|---|---|\n")
            batch["repos"][row["id"]] = {**config.repos[row["id"]], "task": child, "initial": row}
            if row["status"] == "blocked":
                write(folder / "repos" / row["id"] / "preview.json", {"status": "blocked", "reason": row["reason"]})
        parent = fill_task(source, config.control, folder, parent,
                           f"# Core 批量同步 {batch_id}\n\n## 任务契约\n\n- 目标：同一环境内对冻结选集执行并行预览和获批同步。\n- 完成标准：每目标实际验证或明确记录失败/阻塞；不把部分失败视为全批成功。\n- 非目标：不跨环境扇出，不自动提交/推送。\n\n## 当前工作状态\n\n- 固定 Core：{commit}。\n- 编排执行树待用户 Review；内容提案另行合并 Review。\n- 批次私有状态由本轮返回的 batch 定位；不把源检出作为控制工作区。\n\n## 按需上下文地图\n\n| 资源 | 保存内容 | 读取条件 |\n|---|---|---|\n| orchestration/execution-tree.md | 中文批量编排执行树 | 编排 Review 与恢复调度时 |\n| orchestration/plan.json | 对应稳定 Task ID 的并行策略 | 使用 task-orchestration 校验和调度时 |\n")
        batch["task"] = parent
        write(folder / "batch.json", batch)
        execution = Batch(folder)
        root_directory = safe(config.control, parent["path"]).parent
        (root_directory / "orchestration").mkdir()
        (root_directory / "orchestration/execution-tree.md").write_text(execution.render(), encoding="utf-8")
        nodes = [{"task_id": parent["id"], "title": "批量 Core 同步", "children": [r["task"]["id"] for r in batch["repos"].values()],
                  "known_children": [r["task"]["id"] for r in batch["repos"].values()], "mode": "parallel", "depends_on": [],
                  "completion_criteria": ["各项目按批准完成验证，或明确记录未完成项；批次无未说明失败"]}]
        external = {}
        for key, repo in batch["repos"].items():
            deps = []
            if repo["initial"]["status"] == "blocked":
                deps = ["blocked-" + key]
                external[deps[0]] = {"completed": False, "basis": repo["initial"]["reason"]}
            nodes.append({"task_id": repo["task"]["id"], "subtask_key": repo["task"]["subtask_key"], "title": "同步 " + key,
                          "children": [], "known_children": [], "depends_on": deps,
                          "completion_criteria": ["预览只是里程碑；全部获批内容应用、验证并核对安装清单后才可回报完成"],
                          "agent": agent, "display_title": "Core同步 · " + repo["task"]["subtask_key"] + " · " + key,
                          "workspace": "registry:" + key})
        if agent.lower() == "codex":
            for node in nodes[1:]:
                node["session_name"] = node["display_title"]
        plan = plan_tools["resolve"]({"schema": 3, "plan_version": 1, "root_task": parent["id"], "nodes": nodes,
                                      "external_dependencies": external, "max_parallel": parallel},
                                     current_surface, surface, current_source)
        write(root_directory / "orchestration/plan.json", plan)
        return {"batch": str(folder), "source_commit": commit, "task_id": parent["id"], "repos": report["repos"]}


class Batch:
    def __init__(self, folder):
        self.folder = Path(folder).expanduser().resolve()
        self.data = load(self.folder / "batch.json")
        need(self.data["environment"] == environment(), "批次属于另一执行环境")
        self.config = Config(self.data["config_path"])
        need(self.config.fingerprint == self.data["config_digest"], "配置或目标路径已变化，需要新预览/批次")
        need(self.folder.is_relative_to(self.config.control / ".tasks/.state/core-sync") and self.data["control"] == str(self.config.control), "批次不在当前控制工作区")
        need(self.data["globals"] == self.config.globals, "批次系统级目标与冻结配置不符")
        need(set(self.data["repos"]) <= set(self.config.repos) and all(r["path"] == self.config.repos[k]["path"] for k, r in self.data["repos"].items()), "批次项目路径与冻结配置不符")
        self.source = Path(self.data["source"])
        need(self.source.resolve() == self.folder / "source" and not self.source.is_symlink(), "源快照路径不在本批次内")
        need(git(self.source, "rev-parse", "HEAD") == self.data["source_commit"] and not git(self.source, "status", "--porcelain"), "固定源已改变或变脏，停止")
        need(git(self.source, "remote", "get-url", "origin") == self.data["source_origin"], "固定源 origin 已变化")
        self.mapping = copy_map(self.source)

    def repo(self, key):
        need(key in self.data["repos"], "repo 不在冻结选集中")
        return self.data["repos"][key]

    def preview(self, key, proposal=None, observed=()):
        repo, source = self.repo(key), self.source
        root = Path(repo["path"])
        try:
            manifest = installed(repo)
            need(source_id(manifest["source"]) == source_id(self.data["source_origin"]), "项目来源与本轮 Core 不一致")
            base_map = copy_map(source, manifest["source_commit"])
            all_paths = sorted(set(self.mapping) | set(manifest["files"]))
            rows, inputs = [], {}
            for path in all_paths:
                current = state(safe(root, path))
                inputs[path] = current
                ours = current.get("sha256")
                theirs = sha(safe(source, self.mapping[path]).read_bytes()) if path in self.mapping else None
                base = None
                if path in manifest["files"]:
                    need(path in base_map, "旧清单路径不在旧 COPY_MAP 中")
                    base = sha(git(source, "show", f"{manifest['source_commit']}:{base_map[path]}", binary=True))
                    need(base == manifest["files"][path], "清单旧源哈希无法重现，不覆盖")
                if path not in self.mapping:
                    action = "candidate_delete"
                elif ours == theirs:
                    action = "unchanged"
                elif ours == base:
                    action = "add" if base is None else "update"
                elif theirs == base:
                    action = "preserve_local"
                else:
                    action = "conflict"
                recommended_mode = (0o755 if Path(self.mapping[path]).name == "taskctl.py" else 0o644) if path in self.mapping else None
                if action == "unchanged" and current.get("mode") != recommended_mode:
                    action = "mode_review"
                rows.append({"path": path, "action": action, "base": base, "ours": ours, "theirs": theirs,
                             "recommended_mode": recommended_mode, "source_path": self.mapping.get(path)})
            for path in {"AGENTS.override.md", ".tasks/agent-core.json", *observed}:
                inputs[path] = state(safe(root, path))
            semantic = Path(proposal).read_text(encoding="utf-8") if proposal else None
            result = {"status": "ready", "source_commit": self.data["source_commit"], "base_commit": manifest["source_commit"], "inputs": inputs, "files": rows, "proposal": semantic}
        except (ValueError, OSError) as error:
            result = {"status": "blocked", "reason": str(error)}
        with lock(self.folder / "repos" / key / "preview.lock"):
            write(self.folder / "repos" / key / "preview.json", result)
        return result

    def preview_global(self, key):
        need(key in self.data["globals"], "未知系统级目标")
        target = self.data["globals"][key]
        current = state(Path(target["path"]))
        module = runpy.run_path(str(self.source / "scripts/sync_global_agents.py"))
        content = (self.source / "GLOBAL_AGENTS.md").read_bytes()
        try:
            desired, action, details = module["desired_content"](Path(target["path"]).read_bytes() if current["kind"] == "file" else None,
                                                               content, module["source_metadata"](content), target["adopt_local_tail_from"])
            command = [sys.executable, self.source / "scripts/sync_global_agents.py", "--target", target["path"]]
            if target["adopt_local_tail_from"]:
                command += ["--adopt-local-tail-from", target["adopt_local_tail_from"]]
            sync = json.loads(run(command))
            need(sync["source_dirty"] is False, "系统级源不干净")
            result = {"status": "ready", "before": current, "after": {"kind": "file", "sha256": sha(desired), "mode": current.get("mode", 0o644)}, "sync": sync,
                      "desired_content": desired.decode("utf-8")}
        except module["SyncConflict"] as error:
            result = {"status": "blocked", "before": current, "reason": str(error)}
        write(self.folder / "globals" / key / "preview.json", result)
        return result

    def review(self):
        projects, globals_ = {}, {}
        for key in self.data["repos"]:
            path = self.folder / "repos" / key / "preview.json"
            need(path.is_file(), f"{key} 尚未完成预览")
            projects[key] = load(path)
            need(projects[key]["status"] != "ready" or projects[key].get("proposal"), f"{key} 尚未补齐语义提案，不能视为完整 Review")
        for key in self.data["globals"]:
            path = self.folder / "globals" / key / "preview.json"
            need(path.is_file(), f"系统级 {key} 尚未预览")
            globals_[key] = load(path)
        payload = {"source_commit": self.data["source_commit"], "projects": projects, "globals": globals_}
        return {"review_digest": digest(payload), **payload}

    def approve(self, expected, selection, basis):
        need(not (self.folder / "closed.json").exists(), "批次已关闭，不能继续批准")
        review = self.review()
        need(expected == review["review_digest"] and isinstance(basis, str) and basis.strip(), "Review 摘要不符或缺少明确批准依据")
        need(isinstance(selection, dict), "批准选集必须为对象")
        need(isinstance(selection.get("projects", {}), dict) and isinstance(selection.get("globals", []), list), "批准选集格式无效")
        for key, files in selection.get("projects", {}).items():
            need(key in review["projects"], "批准了选集外项目")
            preview = review["projects"][key]
            need(preview["status"] == "ready" and preview.get("proposal"), "项目缺少可审阅的语义提案")
            need(isinstance(files, list) and files and len(files) == len(set(files)), "文件批准选集为空或重复")
            need(set(files) <= {f["path"] for f in preview["files"]}, "批准包含未预览文件")
            self.project_current(key, preview)
        for key in selection.get("globals", []):
            need(key in review["globals"] and review["globals"][key]["status"] == "ready", "系统级目标不存在或预览被阻塞")
            current = state(Path(self.data["globals"][key]["path"]))
            if current != review["globals"][key]["before"]:
                applied = load(self.folder / "globals" / key / "applied.json")
                need(applied["review_digest"] == expected and current == applied["after"] == review["globals"][key]["after"], "系统级输入已变化")
        need(selection.get("projects") or selection.get("globals"), "不能批准空选集")
        record = {"review_digest": expected, "selection": selection, "basis": basis, "approved_at": datetime.now(timezone.utc).isoformat()}
        with lock(self.folder / "approval.lock"):
            write(self.folder / "approvals" / (uuid.uuid4().hex + ".json"), record)
            write(self.folder / "approval.json", record)
        return record

    def project_current(self, key, preview):
        root = Path(self.repo(key)["path"])
        need(preview["status"] == "ready", "项目预览被阻塞")
        for relative, before in preview["inputs"].items():
            need(state(safe(root, relative)) == before, f"{key} 输入已变化：{relative}；重新预览和 Review")

    def approval(self):
        need(not (self.folder / "closed.json").exists(), "批次已关闭，不能继续应用")
        record = load(self.folder / "approval.json")
        need(record["review_digest"] == self.review()["review_digest"], "提案已变化，旧批准失效")
        return record["selection"]

    def gate_global(self, key):
        need(key in self.approval().get("globals", []), "系统级目标未获批准")
        preview = load(self.folder / "globals" / key / "preview.json")
        need(state(Path(self.data["globals"][key]["path"])) == preview["before"], "系统级输入已变化，重新 Review")
        return {"target_id": key, "sync_plan_digest": preview["sync"]["plan_digest"], "apply_allowed": True}

    def record_global(self, key):
        need(key in self.approval().get("globals", []), "系统级目标未获批准")
        preview = load(self.folder / "globals" / key / "preview.json")
        need(state(Path(self.data["globals"][key]["path"])) == preview["after"], "系统级实际结果不符合获批提案")
        write(self.folder / "globals" / key / "applied.json", {"after": preview["after"], "review_digest": self.review()["review_digest"]})
        return {"target_id": key, "verified": True}

    def shared_current(self, approved):
        for global_key, target in self.data["globals"].items():
            before = load(self.folder / "globals" / global_key / "preview.json")
            if global_key in approved.get("globals", []):
                applied = load(self.folder / "globals" / global_key / "applied.json")
                need(applied["review_digest"] == self.review()["review_digest"], "系统级完成记录已失效")
                need(state(Path(target["path"])) == before["after"] == applied["after"], "共享系统级结果发生漂移")
            else:
                need(state(Path(target["path"])) == before["before"], "未批准的系统级输入发生变化")

    def record_project(self, key, result):
        self.repo(key)
        need(isinstance(result, dict) and result.get("outcome") in {"updated", "unchanged", "partial", "failed", "blocked"}, "项目结果 outcome 无效")
        need(isinstance(result.get("evidence"), list) and result["evidence"] and all(isinstance(x, str) and x.strip() for x in result["evidence"]), "结果需要证据入口，不得伪造执行成功")
        preview = load(self.folder / "repos" / key / "preview.json")
        if result["outcome"] in {"updated", "unchanged", "partial"}:
            approved = self.approval()
            need(key in approved.get("projects", {}), "项目未获批准")
            self.shared_current(approved)
            checks = result.get("checks")
            need(isinstance(checks, list) and checks and all(isinstance(c, dict) and c.get("returncode") == 0 and c.get("command") for c in checks), "成功/部分结果需要实际通过的检查记录")
            root = Path(self.repo(key)["path"])
            selected = set(approved["projects"][key])
            for relative, before in preview["inputs"].items():
                if relative not in selected and relative != ".tasks/agent-core.json":
                    need(state(safe(root, relative)) == before, f"未批准文件发生变化：{relative}")
            required = {f["path"] for f in preview["files"] if f["action"] != "unchanged"}
            if result["outcome"] == "partial":
                need(state(safe(root, ".tasks/agent-core.json")) == preview["inputs"][".tasks/agent-core.json"], "部分完成不得推进安装基线")
            else:
                need(required <= selected, "未批准全部必要变化，不能标记完整更新")
                for dest, src in self.mapping.items():
                    actual = state(safe(root, dest))
                    need(actual["kind"] == "file", f"受管文件缺失：{dest}")
                    if Path(src).name == "taskctl.py":
                        need(actual["mode"] & 0o111, f"运行入口丢失可执行位：{dest}")
                if result["outcome"] == "unchanged":
                    need(all(state(safe(root, p)) == before for p, before in preview["inputs"].items() if p != ".tasks/agent-core.json"), "结果标记无需变更，但项目文件实际发生变化")
                manifest = installed(self.repo(key))
                expected = {dest: sha(safe(self.source, src).read_bytes()) for dest, src in self.mapping.items()}
                need(manifest["source_commit"] == self.data["source_commit"] and manifest["files"] == expected
                     and source_id(manifest["source"]) == source_id(self.data["source_origin"]), "实际安装清单不符合固定新源，不记录成功")
        payload = {"result": result, "recorded_at": datetime.now(timezone.utc).isoformat(), "source_commit": self.data["source_commit"]}
        with lock(self.folder / "repos" / key / "result.lock"):
            write(self.folder / "repos" / key / "result.json", payload)
        return payload

    def gate_project(self, key):
        approved = self.approval()
        need(key in approved.get("projects", {}), "项目未获批准")
        preview = load(self.folder / "repos" / key / "preview.json")
        self.project_current(key, preview)
        self.shared_current(approved)
        required = {f["path"] for f in preview["files"] if f["action"] != "unchanged"}
        return {"repo_id": key, "apply_allowed": True, "approved_files": approved["projects"][key],
                "manifest_advance_allowed": required <= set(approved["projects"][key])}

    def render_review(self):
        review = self.review()
        labels = {"unchanged": "无需变更", "update": "可更新", "add": "远端新增", "preserve_local": "保留本地修改", "conflict": "双方修改，需语义合并", "candidate_delete": "候选删除，默认保留", "mode_review": "文件模式差异，需审阅"}
        lines = ["# 本轮具体更新提案", "", "固定 Core：`" + review["source_commit"] + "`", "", "Review 摘要：`" + review["review_digest"] + "`", "", "## 系统级部分"]
        for key, value in review["globals"].items():
            lines += ["", "### " + key]
            if value["status"] != "ready":
                lines.append("阻塞：" + value["reason"])
            else:
                lines += ["同步计划摘要：`" + value["sync"]["plan_digest"] + "`", "", "预期完整内容（本机保留部分包含在内）：", ""]
                lines += ["    " + line for line in value["desired_content"].splitlines()]
        lines += ["", "## 项目级部分"]
        for key, value in review["projects"].items():
            lines += ["", "### " + key]
            if value["status"] != "ready":
                lines.append("阻塞：" + value["reason"])
                continue
            lines += ["旧基线：`" + value["base_commit"] + "`", "", "| 文件 | 比较结果 |", "|---|---|"]
            lines += ["| " + r["path"].replace("|", "／") + " | " + labels[r["action"]] + " |" for r in value["files"]]
            lines += ["", value["proposal"]]
        lines += ["", "请明确批准系统级目标、项目及项目文件；未批准部分不会被 gate 放行。输入变化需重新 Review。"]
        return "\n".join(lines) + "\n"

    def render(self):
        lines = ["# Core 批量更新执行树", "", "固定 Core：`" + self.data["source_commit"] + "`", "", "```text", "本轮批次 [主 Agent 协调；内容 Review 前不写目标]", "├── 系统级预览 [主 Agent 去重处理]"]
        for key in self.data["globals"]:
            lines.append("│   └── " + key)
        lines.append("├── 项目预览 [并行；最多 " + str(self.data["max_parallel"]) + " 个 worker]")
        for key, repo in self.data["repos"].items():
            lines.append(f"│   ├── {repo['task']['subtask_key']} {key} [Agent：{self.data['agent']}；载体：{self.data.get('surface', 'terminal')}；名称：Core同步 · {repo['task']['subtask_key']} · {key}；{('可预览' if repo['initial']['status'] == 'ready' else '阻塞，不启动')}]")
        lines += ["├── 合并更新提案 [用户 Review；可批准部分目标/文件]", "├── 获批系统级变化 [主 Agent 应用、核对结果]", "└── 获批项目 [并行应用与验证；复用对应 Subtask]", "```", "", "编排批准与内容批准分开记录；blocked 目标不启动 worker。每个 worker 在其目标仓库执行，Subtask 入口保存在共享控制工作区。"]
        return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "prepare", "render", "preview", "preview-global", "review", "approve", "gate", "gate-global", "record-global", "record-project", "render-review", "close"))
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/agents-core/repos.json")
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--repo", action="append")
    parser.add_argument("--target")
    parser.add_argument("--proposal-file", type=Path)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--observe", action="append", default=[])
    parser.add_argument("--review-digest")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--basis")
    parser.add_argument("--agent", help="prepare 的本轮 Agent 覆盖，不修改配置")
    parser.add_argument("--max-parallel", type=int, help="prepare 的本轮并发上限覆盖")
    parser.add_argument("--surface", choices=("same", "terminal", "chat"), default="same", help="prepare 的目标载体；默认跟随当前会话")
    parser.add_argument("--current-surface", choices=("terminal", "chat"), help="prepare 使用的已核实当前会话载体")
    parser.add_argument("--current-source", choices=("runtime_verified", "user_declared"), default="user_declared")
    args = parser.parse_args()
    try:
        if args.command in {"inspect", "prepare"}:
            config = Config(args.config)
            result = inspect(config, args.repo) if args.command == "inspect" else prepare(config, args.repo, args.agent, args.max_parallel,
                                                                                     args.surface, args.current_surface, args.current_source)
        else:
            need(args.batch is not None, "需要 --batch")
            if args.command == "close":
                record = args.batch / "batch.json"
                data = load(record if record.exists() else args.batch / "preparation.json")
                need(data["environment"] == environment(), "不能关闭其他环境批次")
                need(args.basis and args.basis.strip(), "关闭批次需要明确依据；先核对所有 worker 已停止/结束")
                write(args.batch / "closed.json", {"basis": args.basis, "closed_at": datetime.now(timezone.utc).isoformat()})
                print(json.dumps({"closed": True, "note": "关闭登记不证明 worker 已停止；由协调者核对实际状态"}, ensure_ascii=False))
                return 0
            batch = Batch(args.batch)
            if args.command in {"render", "render-review"}:
                print(batch.render() if args.command == "render" else batch.render_review(), end="")
                return 0
            if args.command in {"preview", "gate", "record-project"}:
                need(args.repo and len(args.repo) == 1, "此操作需要唯一 --repo")
                if args.command == "record-project":
                    need(args.result_file is not None, "需要 --result-file 的实际验证结果")
                    result = batch.record_project(args.repo[0], load(args.result_file))
                else:
                    result = batch.preview(args.repo[0], args.proposal_file, args.observe) if args.command == "preview" else batch.gate_project(args.repo[0])
            elif args.command in {"preview-global", "gate-global", "record-global"}:
                need(args.target, "需要 --target 的配置 id")
                result = {"preview-global": batch.preview_global, "gate-global": batch.gate_global, "record-global": batch.record_global}[args.command](args.target)
            elif args.command == "review":
                result = batch.review()
            elif args.command == "approve":
                need(args.selection is not None, "需要明确批准选集 --selection")
                result = batch.approve(args.review_digest, load(args.selection), args.basis)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError, StopIteration) as error:
        print(json.dumps({"错误": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
