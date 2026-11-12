from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/task-orchestration/scripts/sessionctl.py"
spec = importlib.util.spec_from_file_location("sessionctl", SCRIPT)
naming = importlib.util.module_from_spec(spec)
spec.loader.exec_module(naming)
SID = "01a1cadf-cc77-7e03-b1bb-513be3327006"
OTHER = "01a1cad0-c3d4-7633-b819-7914dce09196"


class FakeRpc:
    def __init__(self, plan):
        self.plan = plan
        self.name = "Await coordinator instructions"
        self.calls = []
        self.closed = 0
        self.fail_after_set = False
        self.wrong_identity = False
        self.wrong_cwd = False

    def __call__(self, executable, timeout):
        return self

    def close(self):
        self.closed += 1

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "thread/read":
            return {"thread": {"id": params["threadId"], "cwd": self.plan["cwd"] + ("/wrong" if self.wrong_cwd else ""), "name": self.name}}
        if method == "thread/items/list":
            text = " ".join(self.plan[k] for k in ("worker_task_id", "dispatch_id", "marker"))
            if self.wrong_identity:
                text = "unrelated conversation"
            return {"data": [{"turnId": "turn-a", "item": {"type": "userMessage", "content": [{"type": "text", "text": text}]}}]}
        if method == "thread/name/set":
            self.name = params["name"]
            if self.fail_after_set:
                self.fail_after_set = False
                raise naming.Deferred("rpc_connection_closed")
            return {}
        raise AssertionError("Unexpected or disruptive RPC: " + method)

    def mutations(self):
        return sum(method == "thread/name/set" for method, _ in self.calls)


class SessionNamingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="session naming-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = self.directory / "private-store"
        self.plan = {"schema": 1, "task_id": "persistent-task", "attempt_id": "attempt-1", "worker_task_id": "task_actual",
                     "dispatch_id": "ctx_actual", "marker": "UNIQUE_NAMING_MARKER_123456", "environment": naming.environment(),
                     "cwd": str(self.directory), "desired_name": "项目 · S1 · 验证命名"}
        self.binding = {"source": "worker_init", "provider": "codex", "available": True, "thread_id": SID, **naming.scope(self.plan)}
        self.evidence = {"worker_init": self.binding}
        self.rpc = FakeRpc(self.plan)

    def name(self, **kwargs):
        return naming.name_session(self.plan, self.evidence, self.store, rpc_factory=self.rpc, **kwargs)

    def index(self):
        return {"environment": self.plan["environment"], "captured_at": naming.stamp(),
                "status": {"enabled": True, "phase": "current"},
                "search": {"truncated": {k: False for k in ("candidates", "snippets", "query", "freshness")},
                           "hits": [{"sessionId": SID, "evidence": {"snippet": self.plan["marker"]}}]}}

    def test_manual_name_after_lost_reply_is_preserved(self):
        self.rpc.fail_after_set = True
        self.assertEqual(self.name()["status"], "pending")
        self.rpc.name = "用户手动名称"
        self.assertEqual(self.name()["status"], "conflict")
        self.assertEqual(self.rpc.name, "用户手动名称")
        self.assertEqual(self.rpc.mutations(), 1)

    def test_identity_reads_thread_and_keeps_distinct_session_root(self):
        actual = naming.identity(self.plan, {"CODEX_THREAD_ID": SID, "CODEX_SESSION_ID": OTHER, "SECRET": "never-output"})
        self.assertEqual(actual["thread_id"], SID)
        self.assertEqual(actual["session_root_id"], OTHER)
        self.assertNotIn("SECRET", json.dumps(actual))

    def test_root_only_env_is_not_mistaken_for_actual_thread(self):
        actual = naming.identity(self.plan, {"CODEX_SESSION_ID": SID})
        self.assertFalse(actual["available"])
        self.assertNotIn("thread_id", actual)

    def test_runtime_preferred_then_worker_then_index(self):
        runtime = {**self.binding, "source": "runtime"}
        self.evidence = {"runtime": runtime, "worker_init": self.binding, "index": self.index()}
        self.assertEqual(self.name()["source"], "runtime")
        self.evidence["runtime"] = {"available": False}
        self.assertEqual(self.name()["source"], "worker_init")
        second_store = self.directory / "index-store"
        result = naming.name_session(self.plan, {"index": self.index()}, second_store, rpc_factory=self.rpc)
        self.assertEqual(result["source"], "index")

    def test_conflicting_sources_never_rename(self):
        self.evidence["runtime"] = {**self.binding, "thread_id": OTHER}
        result = self.name()
        self.assertEqual(result["reason"], "binding_sources_disagree")
        self.assertEqual(self.rpc.calls, [])

    def test_wrong_dispatch_scope_rejected_before_rpc(self):
        self.binding["dispatch_id"] = "different"
        self.assertIn("scope_mismatch", self.name()["reason"])
        self.assertEqual(self.rpc.mutations(), 0)

    def test_index_disabled_stale_nonunique_and_truncated_defer(self):
        for variant in ("disabled", "stale", "nonunique", "truncated"):
            with self.subTest(variant=variant):
                index = self.index()
                if variant == "disabled":
                    index["status"]["enabled"] = False
                elif variant == "stale":
                    index["captured_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
                elif variant == "nonunique":
                    index["search"]["hits"] *= 2
                else:
                    index["search"]["truncated"]["freshness"] = True
                self.evidence = {"index": index}
                result = self.name()
                self.assertEqual(result["status"], "pending")
                self.assertTrue(result["business_may_continue"])
                self.assertEqual(self.rpc.mutations(), 0)

    def test_index_wrong_environment_and_marker_do_not_rename(self):
        for field in ("environment", "marker"):
            index = self.index()
            if field == "environment":
                index[field] = "other"
            else:
                index["search"]["hits"][0]["evidence"]["snippet"] = "wrong"
            self.evidence = {"index": index}
            self.assertEqual(self.name()["status"], "pending")
        self.assertFalse(self.rpc.calls)

    def test_thread_content_or_cwd_mismatch_prevents_mutation(self):
        self.rpc.wrong_identity = True
        self.assertEqual(self.name()["reason"], "thread_task_identity_mismatch")
        self.rpc.wrong_identity = False
        self.rpc.wrong_cwd = True
        self.assertEqual(self.name()["reason"], "thread_cwd_mismatch")
        self.assertEqual(self.rpc.mutations(), 0)

    def test_rename_is_verified_and_second_call_only_reads(self):
        first = self.name()
        self.assertEqual(first["status"], "verified")
        self.assertTrue(first["changed"])
        second = self.name()
        self.assertEqual(second["status"], "verified")
        self.assertFalse(second["changed"])
        self.assertEqual(self.rpc.mutations(), 1)
        state = json.loads((self.store / (SID + ".json")).read_text())
        self.assertEqual(state["verified_name"], self.plan["desired_name"])
        self.assertEqual(len(state["history"]), 1)
        self.assertEqual((self.store / (SID + ".json")).stat().st_mode & 0o777, 0o600)

    def test_verified_binding_survives_missing_index_without_rediscovery(self):
        self.evidence = {"index": self.index()}
        self.assertEqual(self.name()["status"], "verified")
        self.evidence = {}
        result = self.name()
        self.assertEqual(result["source"], "verified_record")
        self.assertEqual(result["status"], "verified")
        self.assertEqual(self.rpc.mutations(), 1)

    def test_manual_rename_is_not_overwritten(self):
        self.name()
        self.rpc.name = "用户自己的名字"
        result = self.name()
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(self.rpc.name, "用户自己的名字")
        self.assertEqual(self.rpc.mutations(), 1)
        self.assertEqual(json.loads((self.store / (SID + ".json")).read_text())["status"], "conflict")

    def test_title_change_requires_explicit_permission(self):
        self.name()
        self.plan["desired_name"] = "新任务标题"
        self.assertEqual(self.name()["status"], "conflict")
        result = self.name(allow_name_change=True)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(self.rpc.name, "新任务标题")
        self.assertEqual(self.rpc.mutations(), 2)

    def test_lost_set_reply_reconciles_without_resubmitting(self):
        self.rpc.fail_after_set = True
        self.assertEqual(self.name()["status"], "pending")
        self.assertEqual(json.loads((self.store / (SID + ".json")).read_text())["status"], "setting")
        self.assertEqual(self.name()["status"], "verified")
        self.assertEqual(self.rpc.mutations(), 1)

    def test_same_session_two_tasks_cannot_take_ownership(self):
        self.name()
        self.plan["task_id"] = "another-task"
        self.binding["task_id"] = "another-task"
        self.assertEqual(self.name()["reason"], "session_owned_by_other_task")
        self.assertEqual(self.rpc.mutations(), 1)

    def test_changed_session_requires_a_new_attempt(self):
        self.name()
        self.binding["thread_id"] = OTHER
        self.assertEqual(self.name()["reason"], "session_changed_requires_new_attempt")

    def test_missing_id_and_failed_rpc_are_nonblocking_and_recorded(self):
        self.evidence = {}
        result = self.name()
        self.assertEqual(result["status"], "pending")
        self.assertTrue(list((self.store / "attempts").glob("*.json")))
        def unavailable(*_):
            raise OSError("backend unavailable")
        result = naming.name_session(self.plan, {"worker_init": self.binding}, self.store, rpc_factory=unavailable)
        self.assertEqual(result["status"], "pending")
        self.assertTrue(result["business_may_continue"])

    def test_wrong_execution_environment_never_starts_rpc(self):
        self.plan["environment"] = "remote-host"
        self.assertEqual(self.name()["reason"], "wrong_environment")
        self.assertFalse(self.rpc.calls)

    def test_session_lock_does_not_steal_ownership(self):
        self.store.mkdir()
        path = self.store / (SID + ".lock")
        with naming.locked(path):
            self.assertEqual(self.name()["reason"], "naming_busy")
            self.assertTrue(path.exists())
        self.assertFalse(path.exists())
        self.assertEqual(self.rpc.mutations(), 0)

    def test_parallel_same_titles_keep_session_records_separate(self):
        def one(sid):
            evidence = {"worker_init": {**self.binding, "thread_id": sid}}
            rpc = FakeRpc(self.plan)
            return naming.name_session(self.plan, evidence, self.store, rpc_factory=rpc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(one, [SID, OTHER]))
        self.assertEqual({r["thread_id"] for r in results}, {SID, OTHER})
        self.assertTrue(all(r["status"] == "verified" for r in results))
        self.assertTrue((self.store / (SID + ".json")).exists())
        self.assertTrue((self.store / (OTHER + ".json")).exists())

    def test_malformed_candidate_does_not_crash_business(self):
        self.evidence = {"runtime": "not-an-object"}
        self.assertEqual(self.name()["status"], "pending")
        self.assertFalse(self.rpc.calls)

    def test_only_bounded_metadata_methods_are_called(self):
        self.name()
        allowed = {"thread/read", "thread/items/list", "thread/name/set"}
        self.assertTrue(all(method in allowed for method, _ in self.rpc.calls))
        for method, params in self.rpc.calls:
            if method == "thread/read":
                self.assertFalse(params["includeTurns"])
            if method == "thread/items/list":
                self.assertEqual(params["limit"], 4)
        self.assertEqual(self.rpc.closed, 1)

    def test_real_stdio_protocol_and_cli_no_model_turn(self):
        fake = self.directory / "fake codex"
        body = '''#!/usr/bin/env python3
import json,sys
metadata = __METADATA__
text = __TEXT__
for line in sys.stdin:
    request=json.loads(line)
    if 'id' not in request: continue
    method=request['method']
    if method=='initialize': result={}
    elif method=='thread/read': result={'thread':metadata}
    elif method=='thread/items/list': result={'data':[{'item':{'type':'userMessage','content':[{'type':'text','text':text}]}}]}
    elif method=='thread/name/set': metadata['name']=request['params']['name']; result={}
    else:
        print(json.dumps({'id':request['id'],'error':{'code':-32601}}),flush=True); continue
    print(json.dumps({'method':'account/updated','params':{}}),flush=True)
    print(json.dumps({'id':request['id'],'result':result}),flush=True)
'''
        body = body.replace('__METADATA__', repr({"id": SID, "cwd": self.plan["cwd"], "name": "Await coordinator instructions"}))
        body = body.replace('__TEXT__', repr(" ".join(self.plan[k] for k in ("worker_task_id", "dispatch_id", "marker"))))
        fake.write_text(body)
        fake.chmod(0o755)
        plan_path, evidence_path = self.directory / "spec.json", self.directory / "evidence.json"
        plan_path.write_text(json.dumps(self.plan))
        evidence_path.write_text(json.dumps(self.evidence))
        result = subprocess.run([sys.executable, str(SCRIPT), "name", "--spec", str(plan_path), "--evidence", str(evidence_path),
                                 "--store", str(self.store), "--codex", str(fake)], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["status"], "verified")

    def test_rpc_timeout_is_bounded_and_nonblocking(self):
        fake = self.directory / "sleeping-codex"
        fake.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(5)\n')
        fake.chmod(0o755)
        result = naming.name_session(self.plan, self.evidence, self.store, executable=str(fake), timeout=0.1)
        self.assertEqual(result["status"], "pending")
        self.assertIn("timeout", result["reason"])
        self.assertTrue(result["business_may_continue"])


if __name__ == "__main__":
    unittest.main()
