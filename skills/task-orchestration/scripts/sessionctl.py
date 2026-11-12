#!/usr/bin/env python3
"""Codex 无打断会话命名：只用元数据 API，命名失败不阻塞业务。"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import tempfile
import time
import uuid


class Deferred(Exception):
    pass


def need(ok, reason):
    if not ok:
        raise Deferred(reason)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def environment():
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
    return fingerprint([socket.gethostname(), os.getuid(), str(home)])


def thread_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise Deferred("unsupported_or_missing_thread_id") from None


def scope(spec):
    return {k: spec[k] for k in ("task_id", "attempt_id", "worker_task_id", "dispatch_id", "marker", "environment")}


def validate(spec):
    need(isinstance(spec, dict) and spec.get("schema") == 1, "unsupported_spec")
    for key in ("task_id", "attempt_id", "worker_task_id", "dispatch_id", "marker", "environment", "cwd", "desired_name"):
        need(isinstance(spec.get(key), str) and spec[key].strip(), "missing_" + key)
    need(spec["environment"] == environment(), "wrong_environment")
    need(Path(spec["cwd"]).expanduser().is_absolute(), "cwd_must_be_absolute")
    need(len(spec["marker"]) >= 16, "marker_too_short")
    need(len(spec["desired_name"]) <= 200 and not any(ord(c) < 32 for c in spec["desired_name"]), "invalid_name")


def identity(spec, env=None):
    validate(spec)
    env = os.environ if env is None else env
    result = {"schema": 1, "source": "worker_init", "provider": "codex", **scope(spec)}
    try:
        result.update(available=True, thread_id=thread_id(env.get("CODEX_THREAD_ID")))
        if env.get("CODEX_SESSION_ID"):
            result["session_root_id"] = thread_id(env["CODEX_SESSION_ID"])
    except Deferred:
        result.update(available=False, reason="thread_id_environment_unavailable")
    return result


def choose(spec, evidence, now=None):
    need(isinstance(evidence, dict), "invalid_evidence")
    candidates = []
    for source in ("runtime", "worker_init"):
        item = evidence.get(source)
        if item is None:
            continue
        need(isinstance(item, dict), "invalid_" + source)
        if item.get("available") is False:
            continue
        need(item.get("available") is True and item.get("provider") == "codex", "invalid_binding_" + source)
        need(all(item.get(k) == v for k, v in scope(spec).items()), "scope_mismatch_" + source)
        candidates.append((source, thread_id(item.get("thread_id"))))
    if candidates:
        need(len({i[1] for i in candidates}) == 1, "binding_sources_disagree")
        return candidates[0]
    index = evidence.get("index")
    need(isinstance(index, dict), "binding_not_available")
    status, search = index.get("status", {}), index.get("search", {})
    status = status.get("result", status)
    search = search.get("result", search)
    need(index.get("environment") == spec["environment"], "wrong_index_environment")
    need(status.get("enabled") is True and status.get("phase") == "current", "index_not_ready")
    try:
        captured = datetime.fromisoformat(index["captured_at"]).timestamp()
    except (ValueError, TypeError, KeyError):
        raise Deferred("index_timestamp_missing") from None
    now = time.time() if now is None else now
    need(0 <= now - captured <= 120, "index_stale")
    truncated = search.get("truncated")
    need(isinstance(truncated, dict) and all(k in truncated and not truncated[k] for k in ("candidates", "snippets", "query", "freshness")), "index_incomplete")
    hits = search.get("hits")
    need(isinstance(hits, list) and len(hits) == 1, "index_not_unique")
    need(spec["marker"] in hits[0].get("evidence", {}).get("snippet", ""), "index_marker_mismatch")
    return "index", thread_id(hits[0].get("sessionId"))


class Rpc:
    """One short-lived stdio connection; never resumes or submits a model turn."""
    def __init__(self, executable, timeout=10):
        self.deadline = time.monotonic() + timeout
        self.process = subprocess.Popen([executable, "app-server", "--listen", "stdio://"], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer, self.sequence = b"", 0
        try:
            self.call("initialize", {"clientInfo": {"name": "agents_core_session_naming", "version": "1.0"}})
            self.send({"jsonrpc": "2.0", "method": "initialized"})
        except Exception:
            self.close()
            raise

    def send(self, value):
        self.process.stdin.write((json.dumps(value) + "\n").encode())
        self.process.stdin.flush()

    def call(self, method, params):
        need(method in {"initialize", "thread/read", "thread/items/list", "thread/name/set"}, "forbidden_rpc_method")
        self.sequence += 1
        current = self.sequence
        self.send({"jsonrpc": "2.0", "id": current, "method": method, "params": params})
        seen = 0
        while time.monotonic() < self.deadline:
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                seen += len(line)
                need(seen <= 2 * 1024 * 1024, "rpc_response_budget_exceeded")
                try:
                    response = json.loads(line)
                except ValueError:
                    continue
                if response.get("id") == current:
                    need("error" not in response, "rpc_rejected_" + method)
                    return response["result"]
            if self.selector.select(max(0, self.deadline - time.monotonic())):
                data = os.read(self.process.stdout.fileno(), 65536)
                need(bool(data), "rpc_connection_closed")
                self.buffer += data
                need(len(self.buffer) <= 2 * 1024 * 1024, "rpc_response_budget_exceeded")
        raise Deferred("rpc_timeout_" + method)

    def close(self):
        try:
            if self.process.stdin:
                self.process.stdin.close()
            self.process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        finally:
            self.selector.close()
            if self.process.stdout:
                self.process.stdout.close()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".session-name-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextlib.contextmanager
def locked(path):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Deferred("naming_busy") from None
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "at": stamp()}).encode())
        os.close(fd)
        yield
    finally:
        Path(path).unlink(missing_ok=True)


def verify_identity(rpc, spec, sid):
    metadata = rpc.call("thread/read", {"threadId": sid, "includeTurns": False})["thread"]
    need(metadata.get("id") == sid, "thread_id_mismatch")
    need(isinstance(metadata.get("cwd"), str) and bool(metadata["cwd"]) and Path(metadata["cwd"]).resolve() == Path(spec["cwd"]).expanduser().resolve(), "thread_cwd_mismatch")
    # Oldest first, bounded to the first four persisted items; no full-history hydration.
    page = rpc.call("thread/items/list", {"threadId": sid, "sortDirection": "asc", "limit": 4})
    for row in page.get("data", []):
        item = row.get("item", {})
        if item.get("type") == "userMessage":
            text = "".join(c.get("text", "") for c in item.get("content", []))
            need(all(spec[k] in text for k in ("worker_task_id", "dispatch_id", "marker")), "thread_task_identity_mismatch")
            return metadata
    raise Deferred("initial_user_item_unavailable")


def name_session(spec, evidence, store, rpc_factory=Rpc, executable="codex", timeout=10, allow_name_change=False):
    sid, source = None, None
    result = {"status": "pending", "business_may_continue": True}
    try:
        validate(spec)
        store = Path(store)
        attempt_key = fingerprint([spec["task_id"], spec["attempt_id"], environment()])
        cached_path = store / "attempts" / (attempt_key + ".json")
        cached = json.loads(cached_path.read_text()) if cached_path.exists() else {}
        cached_id = cached.get("thread_id")
        saved = {}
        if cached_id:
            cached_id = thread_id(cached_id)
            saved_path = store / (cached_id + ".json")
            saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
        has_live = any(evidence.get(k) is not None and (not isinstance(evidence[k], dict) or evidence[k].get("available") is not False)
                       for k in ("runtime", "worker_init"))
        if not has_live and saved.get("verified_name") and saved.get("proof_fingerprint") == fingerprint(scope(spec)):
            source, sid = "verified_record", cached_id
        else:
            source, sid = choose(spec, evidence)
        sticky = saved.get("task_id") == spec["task_id"] and saved.get("status") in {"setting", "verified", "conflict"}
        need(not sticky or cached_id == sid, "session_changed_requires_new_attempt")
        result.update(thread_id=sid, source=source)
        store.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = store / (sid + ".json")
        with locked(store / (sid + ".lock")):
            record = json.loads(path.read_text()) if path.exists() else {}
            need(not record or record.get("environment") == spec["environment"] and record.get("task_id") == spec["task_id"], "session_owned_by_other_task")
            rpc = rpc_factory(executable, timeout)
            try:
                metadata = verify_identity(rpc, spec, sid)
                desired, current = spec["desired_name"], metadata.get("name")
                if record.get("verified_name"):
                    if desired != record["verified_name"] and not allow_name_change:
                        result.update(status="conflict", reason="planned_name_changed_requires_review")
                        record.update(status="conflict", reason=result["reason"], updated_at=stamp())
                        write(path, record)
                        return result
                    if current != record["verified_name"] and current != desired:
                        result.update(status="conflict", reason="name_changed_externally")
                        record.update(status="conflict", reason=result["reason"], observed_name=current, updated_at=stamp())
                        write(path, record)
                        return result
                if record.get("status") == "setting" and current not in (record.get("previous_name"), desired):
                    result.update(status="conflict", reason="name_changed_externally")
                    record.update(status="conflict", reason=result["reason"], observed_name=current, updated_at=stamp())
                    write(path, record)
                    return result
                history = list(record.get("history", []))
                record.update(schema=1, task_id=spec["task_id"], attempt_id=spec["attempt_id"], environment=spec["environment"],
                              thread_id=sid, source=source, desired_name=desired, proof_fingerprint=fingerprint(scope(spec)), updated_at=stamp())
                if current != desired:
                    record.update(status="setting", previous_name=current, history=history)
                    write(path, record)
                    latest = rpc.call("thread/read", {"threadId": sid, "includeTurns": False})["thread"]
                    need(latest.get("id") == sid and latest.get("name") == current, "name_changed_before_set")
                    rpc.call("thread/name/set", {"threadId": sid, "name": desired})
                    history.append({"before": current, "after": desired, "at": stamp()})
                after = rpc.call("thread/read", {"threadId": sid, "includeTurns": False})["thread"]
                need(after.get("id") == sid and after.get("name") == desired, "rename_not_verified")
                record.update(status="verified", verified_name=desired, verified_at=stamp(), history=history)
                write(path, record)
                result.update(status="verified", name=desired, changed=current != desired)
            finally:
                rpc.close()
    except (Deferred, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        reason = str(error) if isinstance(error, Deferred) else "naming_io_or_protocol_error"
        result.update(status="pending", reason=reason)
    finally:
        try:
            attempt = fingerprint([spec.get("task_id"), spec.get("attempt_id"), environment()])
            write(Path(store) / "attempts" / (attempt + ".json"), {**result, "updated_at": stamp()})
        except (OSError, ValueError, AttributeError, TypeError):
            pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("environment", "identity", "name"))
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--codex", default="codex", help="当前执行主机实际 Codex CLI 路径")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--allow-name-change", action="store_true", help="仅在预期标题变化已获明确 Review 后使用")
    args = parser.parse_args()
    try:
        if args.command == "environment":
            result = {"environment": environment()}
        else:
            need(args.spec is not None, "spec_required")
            spec = json.loads(args.spec.read_text())
            if args.command == "identity":
                result = identity(spec)
            else:
                need(args.evidence is not None and args.store is not None, "evidence_and_store_required")
                need(0 < args.timeout <= 30, "timeout_out_of_range")
                result = name_session(spec, json.loads(args.evidence.read_text()), args.store, executable=args.codex,
                                      timeout=args.timeout, allow_name_change=args.allow_name_change)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (Deferred, OSError, ValueError, KeyError, TypeError, AttributeError):
        print(json.dumps({"status": "pending", "reason": "invalid_naming_input", "business_may_continue": True}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
