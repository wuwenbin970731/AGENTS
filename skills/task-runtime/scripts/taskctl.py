#!/usr/bin/env python3
"""Deterministic local task discovery, loading, and checkpoint updates."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator


VERSION = "0.2.0"
CONFIG_MARKER = "wuwenbin970731/AGENTS"
CURRENT_SCHEMA = 5
WRITABLE_SCHEMAS = {4, 5}
DEFAULT_CONTEXT_MAX_BYTES = 32 * 1024
DEFAULT_CHILD_LIMIT = 8
DEFAULT_TREE_LIMIT = 20
MAX_TREE_DEPTH = 8
MAX_TREE_LIMIT = 100
SUBTASK_KEY_PATTERN = re.compile(r"^S[1-9][0-9]*(?:\.[1-9][0-9]*)*$")
OPEN_STATUSES = {"pending", "in_progress", "awaiting_user", "blocked"}
VALID_STATUSES = OPEN_STATUSES | {"completed"}
VALID_MODES = {"tracked", "rigorous"}
VALID_DESIGN_STATUSES = {
    "not_required",
    "draft",
    "awaiting_user",
    "implementation_ready",
    "implemented",
}
META_FIELDS = (
    "task_schema",
    "id",
    "title",
    "summary",
    "status",
    "mode",
    "design_status",
    "tags",
    "checkpoint",
    "next_action",
    "revision",
    "created_at",
    "updated_at",
    "verified_at",
    "parent_task",
    "subtask_key",
    "depends_on",
)
REQUIRED_V4_FIELDS = {
    "task_schema",
    "id",
    "title",
    "summary",
    "status",
    "mode",
    "design_status",
    "checkpoint",
    "next_action",
    "revision",
    "created_at",
    "updated_at",
}
REQUIRED_V5_FIELDS = REQUIRED_V4_FIELDS | {"parent_task", "subtask_key", "depends_on"}


class TaskCtlError(Exception):
    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".tasks").is_dir() or (candidate / ".git").exists():
            return candidate
    return current


def task_root(project_root: Path) -> Path:
    return project_root / ".tasks"


def state_root(project_root: Path, ensure_writable: bool = False) -> Path:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "--absolute-git-dir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        primary = Path(result.stdout.strip()) / "task-state"
        fallback = task_root(project_root) / ".state"
        if fallback.exists():
            return fallback
        if primary.exists() and not ensure_writable:
            return primary
        if not ensure_writable:
            return primary
        try:
            primary.mkdir(parents=True, exist_ok=True)
            descriptor, probe_name = tempfile.mkstemp(prefix=".write-probe.", dir=primary)
            os.close(descriptor)
            Path(probe_name).unlink(missing_ok=True)
            return primary
        except OSError:
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
    fallback = task_root(project_root) / ".state"
    if ensure_writable:
        fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def require_managed_runtime(project_root: Path) -> None:
    config = task_root(project_root) / "config.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TaskCtlError(f"managed task runtime not found: {config}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise TaskCtlError(f"invalid task runtime config: {config}") from error
    if data.get("managed_by") != CONFIG_MARKER:
        raise TaskCtlError("the project's .tasks directory is not managed by this task runtime")
    if data.get("task_schema") != CURRENT_SCHEMA:
        raise TaskCtlError("unsupported task schema in .tasks/config.json")


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value in {"null", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return value[1:-1].replace("''", "'")
    return value


def split_frontmatter(text: str) -> tuple[dict[str, Any], list[str], int]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise TaskCtlError("TASK.md is missing YAML frontmatter")
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        raise TaskCtlError("TASK.md has an unterminated YAML frontmatter block")

    data: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line.rstrip("\r\n"))
        if match:
            data[match.group(1)] = parse_scalar(match.group(2))
    return data, lines, end


def read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    chunks: list[str] = []
    size = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            chunks.append(line)
            size += len(line.encode("utf-8"))
            if len(chunks) > 1 and line.strip() == "---":
                break
            if size > 65536:
                raise TaskCtlError(f"frontmatter exceeds 64 KiB: {path}")
    fragment = "".join(chunks)
    data, _, _ = split_frontmatter(fragment)
    return data, fragment


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(str(item), ensure_ascii=False) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def update_frontmatter(text: str, updates: dict[str, Any]) -> str:
    _, lines, end = split_frontmatter(text)
    remaining = dict(updates)
    for index in range(1, end):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", lines[index])
        if match and match.group(1) in remaining:
            key = match.group(1)
            lines[index] = f"{key}: {yaml_scalar(remaining.pop(key))}\n"
    if remaining:
        insertion = [f"{key}: {yaml_scalar(value)}\n" for key, value in remaining.items()]
        lines[end:end] = insertion
    return "".join(lines)


def task_paths(project_root: Path) -> list[Path]:
    root = task_root(project_root)
    if not root.exists():
        return []
    resolved_root = root.resolve()
    paths: list[Path] = []
    for path in root.rglob("TASK.md"):
        relative_parts = path.relative_to(root).parts
        if "archive" in relative_parts or "evidence" in relative_parts:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.is_file() or not resolved.is_relative_to(resolved_root):
            continue
        paths.append(path)
    return sorted(paths)


def meta_for(path: Path, project_root: Path) -> dict[str, Any]:
    data, _ = read_frontmatter(path)
    meta = {key: data.get(key) for key in META_FIELDS}
    meta["path"] = str(path.relative_to(project_root))
    return meta


def all_tasks(project_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    result = []
    for path in task_paths(project_root):
        try:
            result.append((path, meta_for(path, project_root)))
        except (OSError, UnicodeError, TaskCtlError):
            continue
    return result


def resolve_task(project_root: Path, identifier: str) -> tuple[Path, dict[str, Any]]:
    raw_path = Path(identifier).expanduser()
    path_candidates = [raw_path, project_root / raw_path]
    for candidate in path_candidates:
        if candidate.is_dir():
            candidate = candidate / "TASK.md"
        if candidate.is_file():
            resolved = candidate.resolve()
            root = task_root(project_root).resolve()
            if not resolved.is_relative_to(root):
                raise TaskCtlError("task path is outside the project's .tasks directory")
            return resolved, meta_for(resolved, project_root)

    exact = [(path, meta) for path, meta in all_tasks(project_root) if meta.get("id") == identifier]
    if len(exact) == 1:
        return exact[0]
    prefix = [(path, meta) for path, meta in all_tasks(project_root) if str(meta.get("id") or "").startswith(identifier)]
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        raise TaskCtlError(f"task identifier is ambiguous: {identifier}")
    raise TaskCtlError(f"task not found: {identifier}")


def emit(value: Any, output_format: str = "json") -> None:
    if output_format == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    rows = value if isinstance(value, list) else [value]
    if output_format == "paths":
        for row in rows:
            print(row.get("path", "") if isinstance(row, dict) else ("" if row is None else row))
        return
    columns = ["subtask_key", "id", "status", "title", "checkpoint", "path"]
    print("\t".join(columns))
    for row in rows:
        if row is None:
            continue
        print("\t".join(str(row.get(column) or "").replace("\t", " ") for column in columns))


def search_score(meta: dict[str, Any], query: str) -> int:
    if not query:
        return 1
    normalized = query.casefold().strip()
    terms = [term for term in re.split(r"[\s,;:/_-]+", normalized) if term]
    fields = {
        "id": str(meta.get("id") or "").casefold(),
        "subtask_key": str(meta.get("subtask_key") or "").casefold(),
        "title": str(meta.get("title") or "").casefold(),
        "summary": str(meta.get("summary") or "").casefold(),
        "tags": " ".join(str(item) for item in (meta.get("tags") or [])).casefold(),
        "checkpoint": str(meta.get("checkpoint") or "").casefold(),
    }
    score = 0
    for field, weight in (("id", 8), ("subtask_key", 8), ("title", 7), ("tags", 5), ("summary", 4), ("checkpoint", 2)):
        if normalized in fields[field]:
            score += weight * 3
        score += weight * sum(1 for term in terms if term in fields[field])
    return score


def parse_context_map(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    inside = False
    rows: list[dict[str, str]] = []
    for line in lines:
        if re.match(r"^##\s+(按需上下文地图|Context Map)\s*$", line, re.IGNORECASE):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside or not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if cells[0].casefold() in {"资源", "resource"}:
            continue
        resource = cells[0].strip("`")
        link = re.fullmatch(r"\[[^]]+\]\(([^)]+)\)", resource)
        if link:
            resource = link.group(1)
        if resource and resource not in {"无", "none", "-"}:
            rows.append({"resource": resource, "summary": cells[1], "read_when": cells[2]})
    return rows


def checked_resource(task_path: Path, resource: str, listed: set[str]) -> Path:
    if resource not in listed:
        raise TaskCtlError("resource is not declared in the TASK.md Context Map")
    candidate = (task_path.parent / resource).resolve()
    task_dir = task_path.parent.resolve()
    if not candidate.is_relative_to(task_dir):
        raise TaskCtlError("resource path escapes the task directory")
    if candidate == task_dir:
        raise TaskCtlError("resource path must identify a file inside the task directory")
    relative_parts = candidate.relative_to(task_dir).parts
    if "subtasks" in relative_parts:
        raise TaskCtlError("resource path crosses a descendant task boundary")
    cursor = candidate.parent
    while cursor != task_dir:
        if (cursor / "TASK.md").is_file():
            raise TaskCtlError("resource path crosses a descendant task boundary")
        cursor = cursor.parent
    if not candidate.is_file():
        raise TaskCtlError(f"resource does not exist: {resource}")
    return candidate


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise TaskCtlError("--slug is required when the title cannot produce an ASCII slug")
    return slug[:64].rstrip("-")


def canonical_subtask_key(value: str) -> str:
    key = value.strip().upper()
    if not SUBTASK_KEY_PATTERN.fullmatch(key):
        raise TaskCtlError("--subtask-key must use S1 or hierarchical forms such as S1.2")
    return key


def subtask_sort_key(meta: dict[str, Any]) -> tuple[tuple[int, ...], str]:
    raw = meta.get("subtask_key")
    if isinstance(raw, str) and SUBTASK_KEY_PATTERN.fullmatch(raw):
        return tuple(int(part) for part in raw[1:].split(".")), str(meta.get("id") or "")
    return (sys.maxsize,), str(meta.get("id") or "")


def direct_children(
    tasks: list[tuple[Path, dict[str, Any]]], parent_id: str
) -> list[tuple[Path, dict[str, Any]]]:
    children = [item for item in tasks if item[1].get("parent_task") == parent_id]
    return sorted(children, key=lambda item: subtask_sort_key(item[1]))


def validate_child_key(parent: dict[str, Any], key: str) -> None:
    parent_key = parent.get("subtask_key")
    if isinstance(parent_key, str) and parent_key:
        expected = re.compile(rf"^{re.escape(parent_key)}\.[1-9][0-9]*$")
        if not expected.fullmatch(key):
            raise TaskCtlError(f"subtask key under {parent_key} must be a direct child such as {parent_key}.1")
    elif not parent.get("parent_task"):
        if not re.fullmatch(r"S[1-9][0-9]*", key):
            raise TaskCtlError("a direct child of a root task must use S1, S2, and so on")


def next_child_key(
    parent: dict[str, Any], children: list[tuple[Path, dict[str, Any]]]
) -> str:
    parent_key = parent.get("subtask_key")
    if isinstance(parent_key, str) and parent_key:
        pattern = re.compile(rf"^{re.escape(parent_key)}\.([1-9][0-9]*)$")
        prefix = f"{parent_key}."
    elif not parent.get("parent_task"):
        pattern = re.compile(r"^S([1-9][0-9]*)$")
        prefix = "S"
    else:
        raise TaskCtlError(
            "a legacy nested parent without subtask_key requires an explicit --subtask-key"
        )
    used = []
    for _, meta in children:
        raw = meta.get("subtask_key")
        match = pattern.fullmatch(str(raw or ""))
        if match:
            used.append(int(match.group(1)))
    return f"{prefix}{max(used, default=0) + 1}"


def task_document(
    args: argparse.Namespace,
    task_id: str,
    timestamp: str,
    parent_task: str | None,
    subtask_key: str | None,
) -> str:
    tags = args.tag or []
    dependencies = args.depends_on or []
    design_status = "draft" if args.mode == "rigorous" else "not_required"
    return f"""---
task_schema: 5
id: {yaml_scalar(task_id)}
title: {yaml_scalar(args.title)}
summary: {yaml_scalar(args.summary)}
status: {args.status}
mode: {args.mode}
design_status: {design_status}
tags: {yaml_scalar(tags)}
checkpoint: {yaml_scalar('任务已创建，尚未完成现场检查')}
next_action: {yaml_scalar('检查相关代码、配置、测试和当前状态')}
revision: 1
created_at: {timestamp}
updated_at: {timestamp}
verified_at: null
parent_task: {yaml_scalar(parent_task)}
subtask_key: {yaml_scalar(subtask_key)}
depends_on: {yaml_scalar(dependencies)}
---

# {args.title}

## 任务契约

- 目标：{args.summary}
- 完成标准：<待补充可验证结果>
- 范围：<待补充>
- 非目标：<待补充>

## 当前工作状态

- 当前正在解决：任务初始化。
- 已确认的关键事实：<待现场检查>
- 当前方案或决定：<待补充>
- 阻塞与解除条件：无。
- 下一次更新 Task 的触发点：形成设计结论或完成首个已验证里程碑。

## 按需上下文地图

| 资源 | 保存内容 | 读取条件 |
|---|---|---|

## 依赖契约

- 依赖任务：{', '.join(dependencies) if dependencies else '无'}
- 当前任务向其他任务提供：<无或内容>
- 当前任务从其他任务消费：<无或内容>
"""


@contextlib.contextmanager
def task_lock(project_root: Path, task_id: str) -> Iterator[None]:
    lock_dir = state_root(project_root, ensure_writable=True) / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{safe_state_key(task_id)}.lock"
    payload = json.dumps({"pid": os.getpid(), "created_at": now_iso()})
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if time.time() - lock_path.stat().st_mtime > 300:
            lock_path.unlink(missing_ok=True)
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        else:
            raise TaskCtlError(f"task is currently being updated: {task_id}", 4)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.close(descriptor)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def atomic_write(path: Path, content: str, mode: int | None = None) -> None:
    if mode is None:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def require_revision(meta: dict[str, Any], expected: int) -> None:
    actual = meta.get("revision")
    if actual != expected:
        raise TaskCtlError(f"revision conflict: expected {expected}, current revision is {actual}", 3)


def validate_common_meta(meta: dict[str, Any], required: set[str]) -> list[str]:
    errors = [f"missing field: {field}" for field in sorted(required - meta.keys())]
    if meta.get("status") not in VALID_STATUSES:
        errors.append("invalid status")
    if meta.get("mode") not in VALID_MODES:
        errors.append("invalid mode")
    if meta.get("design_status") not in VALID_DESIGN_STATUSES:
        errors.append("invalid design_status")
    if not isinstance(meta.get("revision"), int) or meta.get("revision", 0) < 1:
        errors.append("revision must be a positive integer")
    for field in ("id", "title", "summary", "checkpoint", "next_action"):
        value = meta.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")
        elif "\n" in value or "\r" in value:
            errors.append(f"{field} must be one line")
    if not isinstance(meta.get("tags", []), list):
        errors.append("tags must be an inline list")
    if not isinstance(meta.get("depends_on", []), list):
        errors.append("depends_on must be an inline list")
    return errors


def validate_v4_meta(meta: dict[str, Any]) -> list[str]:
    errors = validate_common_meta(meta, REQUIRED_V4_FIELDS)
    if meta.get("task_schema") != 4:
        errors.append("task_schema must be 4")
    return errors


def validate_v5_meta(meta: dict[str, Any]) -> list[str]:
    errors = validate_common_meta(meta, REQUIRED_V5_FIELDS)
    if meta.get("task_schema") != 5:
        errors.append("task_schema must be 5")
    parent = meta.get("parent_task")
    key = meta.get("subtask_key")
    if parent is not None and (not isinstance(parent, str) or not parent.strip()):
        errors.append("parent_task must be null or a non-empty string")
    if parent is None and key is not None:
        errors.append("root task subtask_key must be null")
    if parent is not None:
        if not isinstance(key, str) or not SUBTASK_KEY_PATTERN.fullmatch(key):
            errors.append("child task subtask_key must use S1 or a hierarchical form such as S1.2")
    return errors


def validate_writable_meta(meta: dict[str, Any]) -> list[str]:
    schema = meta.get("task_schema")
    if schema == 4:
        return validate_v4_meta(meta)
    if schema == 5:
        return validate_v5_meta(meta)
    return [f"task schema {schema} is read-only; migrate it before writing"]


def refresh_session(project_root: Path, session: str | None, task_id: str, revision: int) -> None:
    if not session:
        return
    path = session_file(project_root, session, ensure_writable=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = now_iso()
    payload = {
        "task_id": task_id,
        "seen_revision": revision,
        "bound_at": timestamp,
        "last_opened_at": timestamp,
    }
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("task_id") == task_id:
                payload["bound_at"] = previous.get("bound_at", timestamp)
        except (OSError, json.JSONDecodeError):
            pass
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", mode=0o600)


def safe_state_key(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9._-]{1,120}", value):
        return value
    readable = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")[:48] or "state"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{readable}-{digest}"


def estimated_tokens(size_bytes: int) -> int:
    return (size_bytes + 2) // 3


def bounded_limit(value: int, maximum: int = MAX_TREE_LIMIT) -> int:
    if value < 0:
        raise TaskCtlError("--limit must be zero or greater")
    return min(value, maximum)


def compact_tree_meta(
    meta: dict[str, Any], *, child_count: int, tree_depth: int
) -> dict[str, Any]:
    return {
        "id": meta.get("id"),
        "subtask_key": meta.get("subtask_key"),
        "title": meta.get("title"),
        "status": meta.get("status"),
        "summary": meta.get("summary"),
        "checkpoint": meta.get("checkpoint"),
        "parent_task": meta.get("parent_task"),
        "child_count": child_count,
        "tree_depth": tree_depth,
        "path": meta.get("path"),
    }


def emit_bounded_rows(
    rows: list[dict[str, Any]], total: int, output_format: str, **metadata: Any
) -> None:
    if output_format == "json":
        emit(
            {
                **metadata,
                "returned": len(rows),
                "total": total,
                "remaining_count": max(total - len(rows), 0),
                "items": rows,
            },
            output_format,
        )
    else:
        emit(rows, output_format)


def task_graph(
    project_root: Path,
) -> tuple[
    list[tuple[Path, dict[str, Any]]],
    dict[str, tuple[Path, dict[str, Any]]],
    dict[str, list[tuple[Path, dict[str, Any]]]],
]:
    tasks = all_tasks(project_root)
    by_id = {
        str(meta.get("id")): (path, meta)
        for path, meta in tasks
        if isinstance(meta.get("id"), str) and meta.get("id")
    }
    children: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for item in tasks:
        parent = item[1].get("parent_task")
        if isinstance(parent, str) and parent:
            children.setdefault(parent, []).append(item)
    for values in children.values():
        values.sort(key=lambda item: subtask_sort_key(item[1]))
    return tasks, by_id, children


def cmd_search(args: argparse.Namespace) -> None:
    statuses = VALID_STATUSES if args.all else set(args.status or OPEN_STATUSES)
    rows = []
    for _, meta in all_tasks(args.project_root):
        if meta.get("status") not in statuses:
            continue
        score = search_score(meta, args.query or "")
        if score:
            row = dict(meta)
            row["score"] = score
            rows.append(row)
    rows.sort(key=lambda item: (item["score"], str(item.get("updated_at") or "")), reverse=True)
    for row in rows:
        row.pop("score", None)
    emit(rows[: min(max(args.limit, 0), 8)], args.format)


def cmd_show(args: argparse.Namespace) -> None:
    path, meta = resolve_task(args.project_root, args.task)
    if args.entry:
        sys.stdout.write(path.read_text(encoding="utf-8"))
    else:
        emit(meta, args.format)


def cmd_new(args: argparse.Namespace) -> None:
    for field in ("title", "summary"):
        if "\n" in getattr(args, field) or "\r" in getattr(args, field):
            raise TaskCtlError(f"--{field.replace('_', '-')} must be one line")
    root = task_root(args.project_root)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().astimezone().replace(microsecond=0)
    slug = safe_slug(args.slug or args.title)
    if args.subtask_key and not args.parent:
        raise TaskCtlError("--subtask-key requires --parent")

    parent_path: Path | None = None
    parent_meta: dict[str, Any] | None = None
    if args.parent:
        parent_path, parent_meta = resolve_task(args.project_root, args.parent)

    def create(parent_key: str | None) -> Path:
        key_component = f"-{parent_key.casefold()}" if parent_key else ""
        task_id = f"{timestamp:%Y-%m-%d-%H%M%S}{key_component}-{slug}"
        if any(meta.get("id") == task_id for _, meta in all_tasks(args.project_root)):
            raise TaskCtlError(f"task already exists: {task_id}")
        if parent_path is None:
            directory = root / f"{timestamp:%Y-%m-%d}" / task_id
        else:
            directory = parent_path.parent / "subtasks" / task_id
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError as error:
            raise TaskCtlError(
                f"task directory already exists: {directory.relative_to(args.project_root)}"
            ) from error
        path = directory / "TASK.md"
        atomic_write(
            path,
            task_document(
                args,
                task_id,
                timestamp.isoformat(),
                str(parent_meta["id"]) if parent_meta else None,
                parent_key,
            ),
        )
        return path

    if parent_meta is None:
        path = create(None)
    else:
        parent_id = str(parent_meta["id"])
        with task_lock(args.project_root, parent_id):
            tasks = all_tasks(args.project_root)
            children = direct_children(tasks, parent_id)
            key = canonical_subtask_key(args.subtask_key) if args.subtask_key else next_child_key(parent_meta, children)
            validate_child_key(parent_meta, key)
            if any(meta.get("subtask_key") == key for _, meta in children):
                raise TaskCtlError(f"subtask key already exists under {parent_id}: {key}")
            path = create(key)
    emit(meta_for(path, args.project_root), args.format)


def cmd_context_list(args: argparse.Namespace) -> None:
    path, _ = resolve_task(args.project_root, args.task)
    rows = parse_context_map(path.read_text(encoding="utf-8"))
    listed = {row["resource"] for row in rows}
    for row in rows:
        try:
            target = checked_resource(path, row["resource"], listed)
            size = target.stat().st_size
            row.update(
                {
                    "available": True,
                    "size_bytes": size,
                    "estimated_tokens": estimated_tokens(size),
                }
            )
        except (OSError, TaskCtlError) as error:
            row.update(
                {
                    "available": False,
                    "size_bytes": None,
                    "estimated_tokens": None,
                    "error": str(error),
                }
            )
    emit(rows, args.format)


def cmd_context_read(args: argparse.Namespace) -> None:
    path, _ = resolve_task(args.project_root, args.task)
    resources = parse_context_map(path.read_text(encoding="utf-8"))
    listed = {row["resource"] for row in resources}
    target = checked_resource(path, args.resource, listed)
    if args.max_tokens is not None:
        if args.max_tokens <= 0:
            raise TaskCtlError("--max-tokens must be positive")
        max_bytes = args.max_tokens * 3
    else:
        max_bytes = args.max_bytes
    if max_bytes <= 0:
        raise TaskCtlError("--max-bytes must be positive")
    size = target.stat().st_size
    if size > max_bytes:
        raise TaskCtlError(
            f"resource exceeds read budget: {size} bytes, approximately "
            f"{estimated_tokens(size)} tokens; budget is {max_bytes} bytes"
        )
    content = target.read_text(encoding="utf-8")
    actual_size = len(content.encode("utf-8"))
    if actual_size > max_bytes:
        raise TaskCtlError(
            f"resource changed and exceeds read budget: {actual_size} bytes, approximately "
            f"{estimated_tokens(actual_size)} tokens; budget is {max_bytes} bytes"
        )
    sys.stdout.write(content)


def cmd_children(args: argparse.Namespace) -> None:
    _, selected = resolve_task(args.project_root, args.task)
    tasks, _, children = task_graph(args.project_root)
    selected_id = str(selected["id"])
    direct = children.get(selected_id, [])
    counts = {
        str(meta.get("id")): len(children.get(str(meta.get("id")), []))
        for _, meta in tasks
    }
    limit = bounded_limit(args.limit)
    rows = [
        compact_tree_meta(meta, child_count=counts.get(str(meta.get("id")), 0), tree_depth=1)
        for _, meta in direct[:limit]
    ]
    emit_bounded_rows(rows, len(direct), args.format, parent_task=selected_id)


def cmd_lineage(args: argparse.Namespace) -> None:
    _, selected = resolve_task(args.project_root, args.task)
    tasks, by_id, children = task_graph(args.project_root)
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = selected
    while True:
        task_id = str(current.get("id"))
        if task_id in seen:
            raise TaskCtlError(f"parent cycle detected at {task_id}")
        seen.add(task_id)
        chain.append(current)
        parent = current.get("parent_task")
        if not parent:
            break
        parent_item = by_id.get(str(parent))
        if parent_item is None:
            raise TaskCtlError(f"parent task not found: {parent}")
        current = parent_item[1]
    chain.reverse()
    counts = {
        str(meta.get("id")): len(children.get(str(meta.get("id")), []))
        for _, meta in tasks
    }
    all_rows = [
        compact_tree_meta(meta, child_count=counts.get(str(meta.get("id")), 0), tree_depth=depth)
        for depth, meta in enumerate(chain)
    ]
    limit = bounded_limit(args.limit)
    if len(all_rows) <= limit:
        rows = all_rows
    elif limit == 0:
        rows = []
    elif limit == 1:
        rows = [all_rows[-1]]
    else:
        rows = [all_rows[0], *all_rows[-(limit - 1) :]]
    emit_bounded_rows(rows, len(all_rows), args.format, task=str(selected["id"]))


def cmd_tree(args: argparse.Namespace) -> None:
    _, selected = resolve_task(args.project_root, args.task)
    if args.depth < 0 or args.depth > MAX_TREE_DEPTH:
        raise TaskCtlError(f"--depth must be between 0 and {MAX_TREE_DEPTH}")
    tasks, _, children = task_graph(args.project_root)
    counts = {
        str(meta.get("id")): len(children.get(str(meta.get("id")), []))
        for _, meta in tasks
    }
    rows: list[dict[str, Any]] = []
    active: set[str] = set()

    def visit(meta: dict[str, Any], depth: int) -> None:
        task_id = str(meta.get("id"))
        if task_id in active:
            raise TaskCtlError(f"parent cycle detected at {task_id}")
        rows.append(
            compact_tree_meta(meta, child_count=counts.get(task_id, 0), tree_depth=depth)
        )
        if depth >= args.depth:
            return
        active.add(task_id)
        for _, child in children.get(task_id, []):
            visit(child, depth + 1)
        active.remove(task_id)

    visit(selected, 0)
    total = len(rows)
    limit = bounded_limit(args.limit)
    emit_bounded_rows(
        rows[:limit], total, args.format, root_task=str(selected["id"]), max_depth=args.depth
    )


def cmd_related(args: argparse.Namespace) -> None:
    _, selected = resolve_task(args.project_root, args.task)
    selected_id = selected.get("id")
    referenced = set(selected.get("depends_on") or [])
    if selected.get("parent_task"):
        referenced.add(selected["parent_task"])
    rows = []
    for _, meta in all_tasks(args.project_root):
        task_id = meta.get("id")
        reverse = selected_id == meta.get("parent_task") or selected_id in (meta.get("depends_on") or [])
        if task_id in referenced or reverse:
            rows.append(meta)
    rows.sort(key=subtask_sort_key)
    emit(rows[: bounded_limit(args.limit)], args.format)


def cmd_update(args: argparse.Namespace) -> None:
    path, original_meta = resolve_task(args.project_root, args.task)
    with task_lock(args.project_root, str(original_meta.get("id"))):
        text = path.read_text(encoding="utf-8")
        current, _, _ = split_frontmatter(text)
        require_revision(current, args.expect_revision)
        updates: dict[str, Any] = {
            "revision": args.expect_revision + 1,
            "updated_at": now_iso(),
        }
        for field in ("status", "design_status", "checkpoint", "next_action"):
            value = getattr(args, field)
            if value is not None:
                updates[field] = value
        if args.verified_now:
            updates["verified_at"] = now_iso()
        proposed = update_frontmatter(text, updates)
        proposed_meta, _, proposed_end = split_frontmatter(proposed)
        validation_errors = validate_writable_meta(proposed_meta)
        frontmatter_bytes = len("".join(proposed.splitlines(keepends=True)[: proposed_end + 1]).encode("utf-8"))
        if frontmatter_bytes > 1024:
            validation_errors.append(f"frontmatter exceeds 1 KiB: {frontmatter_bytes} bytes")
        if validation_errors:
            raise TaskCtlError("invalid task update: " + "; ".join(validation_errors))
        atomic_write(path, proposed)
    updated_meta = meta_for(path, args.project_root)
    refresh_session(args.project_root, args.session, str(updated_meta["id"]), int(updated_meta["revision"]))
    emit(updated_meta, args.format)


def cmd_write(args: argparse.Namespace) -> None:
    path, original_meta = resolve_task(args.project_root, args.task)
    proposed = Path(args.from_file).read_text(encoding="utf-8")
    proposed_meta, _, _ = split_frontmatter(proposed)
    if proposed_meta.get("id") != original_meta.get("id"):
        raise TaskCtlError("proposed TASK.md changes the task id")
    if proposed_meta.get("task_schema") != original_meta.get("task_schema"):
        raise TaskCtlError("proposed TASK.md changes the task schema; use an explicit migration")
    if original_meta.get("task_schema") == 5:
        for field in ("parent_task", "subtask_key"):
            if proposed_meta.get(field) != original_meta.get(field):
                raise TaskCtlError(f"proposed TASK.md changes immutable field: {field}")
    validation_errors = validate_writable_meta(proposed_meta)
    if validation_errors:
        raise TaskCtlError("invalid proposed TASK.md: " + "; ".join(validation_errors))
    _, _, proposed_end = split_frontmatter(proposed)
    frontmatter_bytes = len("".join(proposed.splitlines(keepends=True)[: proposed_end + 1]).encode("utf-8"))
    if frontmatter_bytes > 1024:
        raise TaskCtlError(f"proposed frontmatter exceeds 1 KiB: {frontmatter_bytes} bytes")
    if len(proposed.splitlines()) > 240:
        raise TaskCtlError("proposed TASK.md exceeds 240 lines")
    with task_lock(args.project_root, str(original_meta.get("id"))):
        current_text = path.read_text(encoding="utf-8")
        current, _, _ = split_frontmatter(current_text)
        require_revision(current, args.expect_revision)
        proposed = update_frontmatter(
            proposed,
            {"revision": args.expect_revision + 1, "updated_at": now_iso()},
        )
        atomic_write(path, proposed)
    updated_meta = meta_for(path, args.project_root)
    refresh_session(args.project_root, args.session, str(updated_meta["id"]), int(updated_meta["revision"]))
    emit(updated_meta, args.format)


def session_file(project_root: Path, session: str, ensure_writable: bool = False) -> Path:
    if not session:
        raise TaskCtlError("session id is empty")
    return state_root(project_root, ensure_writable=ensure_writable) / "sessions" / f"{safe_state_key(session)}.json"


def cmd_bind(args: argparse.Namespace) -> None:
    _, meta = resolve_task(args.project_root, args.task)
    path = session_file(args.project_root, args.session, ensure_writable=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": meta["id"],
        "seen_revision": meta.get("revision"),
        "bound_at": now_iso(),
        "last_opened_at": now_iso(),
    }
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", mode=0o600)
    emit(payload, args.format)


def cmd_current(args: argparse.Namespace) -> None:
    path = session_file(args.project_root, args.session)
    if not path.exists():
        emit(None, args.format)
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        task_id = payload["task_id"]
    except (OSError, json.JSONDecodeError, KeyError) as error:
        raise TaskCtlError(f"invalid session binding: {path}") from error
    _, meta = resolve_task(args.project_root, task_id)
    payload["stale"] = payload.get("seen_revision") != meta.get("revision")
    payload["task"] = meta
    emit(payload, args.format)


def cmd_unbind(args: argparse.Namespace) -> None:
    path = session_file(args.project_root, args.session)
    existed = path.exists()
    path.unlink(missing_ok=True)
    emit({"session": args.session, "removed": existed}, args.format)


def cmd_doctor(args: argparse.Namespace) -> None:
    issues: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    records: list[tuple[Path, dict[str, Any]]] = []
    root = task_root(args.project_root)

    def issue(level: str, path: Path | str, message: str) -> None:
        rendered = str(path.relative_to(args.project_root)) if isinstance(path, Path) else path
        issues.append({"level": level, "path": rendered, "message": message})

    config = root / "config.json"
    if not config.exists():
        issue("warning", config, "missing runtime config")
    else:
        try:
            config_data = json.loads(config.read_text(encoding="utf-8"))
            if config_data.get("managed_by") != CONFIG_MARKER:
                issue("error", config, "unexpected managed_by marker")
            if config_data.get("task_schema") != CURRENT_SCHEMA:
                issue("error", config, f"config task_schema must be {CURRENT_SCHEMA}")
            if config_data.get("runtime_version") != VERSION:
                issue("warning", config, f"runtime_version differs from taskctl {VERSION}")
        except (OSError, json.JSONDecodeError) as error:
            issue("error", config, f"invalid runtime config: {error}")
    for relative in ("TASK_WORKFLOW.md", "TASK_TEMPLATE.md", "TASK_ITERATION_TEMPLATE.md", "bin/taskctl"):
        expected = root / relative
        if not expected.is_file():
            issue("warning", expected, "missing runtime file")
    installed_cli = root / "bin/taskctl"
    if installed_cli.is_file() and not os.access(installed_cli, os.X_OK):
        issue("error", installed_cli, "taskctl is not executable")
    paths = task_paths(args.project_root)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            meta, _, end = split_frontmatter(text)
        except (OSError, UnicodeError, TaskCtlError) as error:
            issue("error", path, str(error))
            continue
        records.append((path, meta))
        task_id = str(meta.get("id") or "")
        if task_id in seen:
            issue("error", path, f"duplicate id also used by {seen[task_id]}")
        elif task_id:
            seen[task_id] = str(path.relative_to(args.project_root))
        schema = meta.get("task_schema")
        if schema in WRITABLE_SCHEMAS:
            for message in validate_writable_meta(meta):
                issue("error", path, message)
        else:
            issue("warning", path, f"legacy task schema: {schema}")
        if schema not in WRITABLE_SCHEMAS and meta.get("status") not in VALID_STATUSES:
            issue("error", path, "invalid status")
        frontmatter_bytes = len("".join(text.splitlines(keepends=True)[: end + 1]).encode("utf-8"))
        if frontmatter_bytes > 1024:
            issue("warning", path, f"frontmatter exceeds 1 KiB: {frontmatter_bytes} bytes")
        line_count = len(text.splitlines())
        if line_count > 240:
            issue("error", path, f"TASK.md exceeds 240 lines: {line_count}")
        elif line_count > 160:
            issue("warning", path, f"TASK.md exceeds 160 lines: {line_count}")
        relative_length = len(str(path.relative_to(args.project_root)))
        if relative_length > 240:
            issue("warning", path, f"task path exceeds 240 characters: {relative_length}")
        for row in parse_context_map(text):
            try:
                checked_resource(path, row["resource"], {row["resource"]})
            except TaskCtlError as error:
                issue("error", path, str(error))

    by_id = {
        str(meta.get("id")): (path, meta)
        for path, meta in records
        if isinstance(meta.get("id"), str) and meta.get("id") and str(meta.get("id")) in seen
    }
    sibling_keys: dict[tuple[str, str], Path] = {}
    for path, meta in records:
        task_id = str(meta.get("id") or "")
        parent_id = meta.get("parent_task")
        if not isinstance(parent_id, str) or not parent_id:
            if meta.get("task_schema") == 5 and "subtasks" in path.relative_to(root).parts:
                issue("error", path, "root schema 5 task cannot live below a subtasks directory")
            continue
        parent_item = by_id.get(parent_id)
        if parent_item is None:
            level = "error" if meta.get("task_schema") == 5 else "warning"
            issue(level, path, f"parent task not found: {parent_id}")
            continue
        parent_path, parent_meta = parent_item
        if meta.get("task_schema") != 5:
            continue
        key = str(meta.get("subtask_key") or "")
        duplicate = sibling_keys.get((parent_id, key))
        if duplicate is not None:
            issue("error", path, f"duplicate subtask_key {key} also used by {duplicate.relative_to(args.project_root)}")
        else:
            sibling_keys[(parent_id, key)] = path
        parent_key = parent_meta.get("subtask_key")
        if isinstance(parent_key, str) and parent_key:
            if not re.fullmatch(rf"{re.escape(parent_key)}\.[1-9][0-9]*", key):
                issue("error", path, f"subtask_key must be a direct child of {parent_key}")
        elif not parent_meta.get("parent_task"):
            if not re.fullmatch(r"S[1-9][0-9]*", key):
                issue("error", path, "direct child of a root task must use S1, S2, and so on")
        expected = parent_path.parent / "subtasks" / task_id / "TASK.md"
        if path.resolve() != expected.resolve():
            issue(
                "error",
                path,
                f"schema 5 child path must be {expected.relative_to(args.project_root)}",
            )

    reported_cycles: set[tuple[str, ...]] = set()
    for path, meta in records:
        task_id = str(meta.get("id") or "")
        chain: list[str] = []
        positions: dict[str, int] = {}
        current = task_id
        while current in by_id:
            if current in positions:
                cycle = tuple(chain[positions[current] :])
                signature = tuple(sorted(cycle))
                if signature not in reported_cycles:
                    reported_cycles.add(signature)
                    issue("error", path, "parent cycle detected: " + " -> ".join((*cycle, cycle[0])))
                break
            positions[current] = len(chain)
            chain.append(current)
            parent = by_id[current][1].get("parent_task")
            if not isinstance(parent, str) or not parent:
                break
            current = parent
        depth = max(len(chain) - 1, 0)
        if depth > 5:
            issue("warning", path, f"task nesting depth is {depth}; consider splitting the hierarchy")
    errors = sum(issue["level"] == "error" for issue in issues)
    emit({"tasks": len(paths), "errors": errors, "warnings": len(issues) - errors, "issues": issues}, args.format)
    if errors:
        raise SystemExit(1)


def add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("json", "table", "paths"), default="json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskctl", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--root", type=Path, help="project root; defaults to automatic discovery")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="search task metadata without reading task bodies")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--status", action="append", choices=sorted(VALID_STATUSES))
    search.add_argument("--all", action="store_true")
    search.add_argument("--limit", type=int, default=8)
    add_format(search)
    search.set_defaults(func=cmd_search)

    show = subparsers.add_parser("show", help="show one task's metadata or entry document")
    show.add_argument("task")
    show.add_argument("--entry", action="store_true", help="print TASK.md; links are not expanded")
    add_format(show)
    show.set_defaults(func=cmd_show)

    new = subparsers.add_parser("new", help="create a schema 5 task")
    new.add_argument("title")
    new.add_argument("--summary", required=True)
    new.add_argument("--slug")
    new.add_argument("--mode", choices=sorted(VALID_MODES), default="tracked")
    new.add_argument("--status", choices=("pending", "in_progress"), default="in_progress")
    new.add_argument("--tag", action="append")
    new.add_argument("--parent")
    new.add_argument("--subtask-key", help="stable hierarchy key such as S1 or S1.2")
    new.add_argument("--depends-on", action="append")
    add_format(new)
    new.set_defaults(func=cmd_new)

    related = subparsers.add_parser("related", help="show metadata for directly related tasks")
    related.add_argument("task")
    related.add_argument("--limit", type=int, default=DEFAULT_CHILD_LIMIT)
    add_format(related)
    related.set_defaults(func=cmd_related)

    children = subparsers.add_parser("children", help="show bounded L0 metadata for direct child tasks")
    children.add_argument("task")
    children.add_argument("--limit", type=int, default=DEFAULT_CHILD_LIMIT)
    add_format(children)
    children.set_defaults(func=cmd_children)

    tree = subparsers.add_parser("tree", help="show a bounded L0 task subtree")
    tree.add_argument("task")
    tree.add_argument("--depth", type=int, default=1)
    tree.add_argument("--limit", type=int, default=DEFAULT_TREE_LIMIT)
    add_format(tree)
    tree.set_defaults(func=cmd_tree)

    lineage = subparsers.add_parser("lineage", help="show bounded L0 ancestors and the selected task")
    lineage.add_argument("task")
    lineage.add_argument("--limit", type=int, default=DEFAULT_TREE_LIMIT)
    add_format(lineage)
    lineage.set_defaults(func=cmd_lineage)

    context_parser = subparsers.add_parser("context", help="list or explicitly read declared resources")
    context_commands = context_parser.add_subparsers(dest="context_command", required=True)
    context_list = context_commands.add_parser("list")
    context_list.add_argument("task")
    add_format(context_list)
    context_list.set_defaults(func=cmd_context_list)
    context_read = context_commands.add_parser("read")
    context_read.add_argument("task")
    context_read.add_argument("resource")
    budget = context_read.add_mutually_exclusive_group()
    budget.add_argument("--max-bytes", type=int, default=DEFAULT_CONTEXT_MAX_BYTES)
    budget.add_argument("--max-tokens", type=int)
    context_read.set_defaults(func=cmd_context_read)

    update = subparsers.add_parser("update", help="atomically update task checkpoint metadata")
    update.add_argument("task")
    update.add_argument("--expect-revision", type=int, required=True)
    update.add_argument("--status", choices=sorted(VALID_STATUSES))
    update.add_argument("--design-status", choices=sorted(VALID_DESIGN_STATUSES))
    update.add_argument("--checkpoint")
    update.add_argument("--next-action")
    update.add_argument("--verified-now", action="store_true")
    update.add_argument("--session", help="refresh this local session binding after a successful write")
    add_format(update)
    update.set_defaults(func=cmd_update)

    write = subparsers.add_parser("write", help="atomically replace TASK.md with revision checking")
    write.add_argument("task")
    write.add_argument("--from", dest="from_file", required=True)
    write.add_argument("--expect-revision", type=int, required=True)
    write.add_argument("--session", help="refresh this local session binding after a successful write")
    add_format(write)
    write.set_defaults(func=cmd_write)

    bind = subparsers.add_parser("bind", help="bind one local session to a task")
    bind.add_argument("task")
    bind.add_argument("--session", required=True)
    add_format(bind)
    bind.set_defaults(func=cmd_bind)
    current = subparsers.add_parser("current", help="show the task bound to a local session")
    current.add_argument("--session", required=True)
    add_format(current)
    current.set_defaults(func=cmd_current)
    unbind = subparsers.add_parser("unbind", help="remove a local session binding")
    unbind.add_argument("--session", required=True)
    add_format(unbind)
    unbind.set_defaults(func=cmd_unbind)

    doctor = subparsers.add_parser("doctor", help="validate task structure and disclosure boundaries")
    add_format(doctor)
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.project_root = find_project_root(args.root or Path.cwd())
    try:
        if args.command != "doctor":
            require_managed_runtime(args.project_root)
        args.func(args)
        return 0
    except TaskCtlError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
