from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/task-orchestration/scripts/planctl.py"
spec = importlib.util.spec_from_file_location("planctl", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Plan = module.Plan


def node(key, children=(), mode=None):
    value = {"task_id": key, "subtask_key": key, "title": "任务" + key,
             "children": list(children), "known_children": list(children),
             "completion_criteria": ["检查通过并提供证据"], "depends_on": []}
    if mode:
        value["mode"] = mode
    if not children:
        value.update(agent="codex", terminal_title="示例 · " + key, workspace="current")
    return value


def example():
    return {"schema": 2, "plan_version": 1, "root_task": "root", "nodes": [
        node("root", ["S1", "S2"]), node("S1", ["S1.1", "S1.2"], "parallel"),
        node("S1.1"), node("S1.2"), node("S2", ["S2.1", "S2.2"], "auto-sequential"),
        node("S2.1"), node("S2.2")], "external_dependencies": {}}


def approved(data):
    plan = Plan(data)
    data["review"] = {"status": "approved", "plan_version": data["plan_version"], "plan_digest": plan.digest, "basis": "用户批准执行树", "artifact": "orchestration/example-v1.md"}
    data["authorization"] = {"state": "authorized", "basis": "用户要求执行"}
    return Plan(data)


def report(actor=None):
    value = {"phase": "reported", "outcome": "succeeded", "evidence": ["evidence/checks.md"]}
    if actor:
        value["acceptance"] = {"status": "accepted", "actor": actor, "basis": "已核对交付条件"}
    return value


class DescendantPlanTest(unittest.TestCase):
    def setUp(self):
        self.data = example()
        self.plan = approved(self.data)
        self.runtime = {"plan_digest": self.plan.digest, "nodes": {}}

    def ready(self):
        return self.plan.frontier(self.runtime)

    def accepted_backend(self):
        self.runtime["nodes"].update({"S1.1": report("coordinator"), "S1.2": report("coordinator")})

    def test_mixed_tree_advances_only_after_aggregate_and_user_acceptance(self):
        self.assertEqual(self.ready()["launch"], ["S1.1", "S1.2"])
        self.accepted_backend()
        self.assertEqual(self.ready()["aggregate"], [{"task_id": "S1", "task_completion_allowed": True}])
        self.assertEqual(self.ready()["launch"], [])
        self.runtime["nodes"]["S1"] = report()
        self.assertEqual(self.ready()["accept"][0]["actor"], "user")
        self.runtime["nodes"]["S1"] = report("user")
        self.assertEqual(self.ready()["launch"], ["S2.1"])
        self.runtime["nodes"]["S2.1"] = report("coordinator")
        self.assertEqual(self.ready()["launch"], ["S2.2"])
        self.runtime["nodes"]["S2.2"] = report("coordinator")
        self.assertEqual(self.ready()["aggregate"][0]["task_id"], "S2")
        self.runtime["nodes"]["S2"] = report("user")
        self.assertEqual(self.ready()["aggregate"][0]["task_id"], "root")
        self.runtime["nodes"]["root"] = report("user")
        self.assertTrue(self.ready()["batch_complete"])

    def test_nested_mode_inheritance_and_override(self):
        self.data["nodes"][1].pop("mode")
        plan = approved(self.data)
        runtime = {"plan_digest": plan.digest, "nodes": {}}
        self.assertEqual(plan.mode["S1.2"], "manual-sequential")
        self.assertEqual(plan.mode["S2.2"], "auto-sequential")
        self.assertEqual(plan.frontier(runtime)["launch"], ["S1.1"])
        runtime["nodes"]["S1.1"] = report("user")
        self.assertEqual(plan.frontier(runtime)["launch"], ["S1.2"])

    def test_cross_branch_dependency_blocks_only_affected_parallel_leaf(self):
        self.data["nodes"][0]["mode"] = "parallel"
        self.data["nodes"][5]["depends_on"] = ["S1.1"]
        plan = approved(self.data)
        runtime = {"plan_digest": plan.digest, "nodes": {}}
        self.assertEqual(plan.frontier(runtime)["launch"], ["S1.1", "S1.2"])
        runtime["nodes"]["S1.1"] = report("coordinator")
        self.assertEqual(plan.frontier(runtime)["launch"], ["S1.2", "S2.1"])

    def test_partial_selection_does_not_claim_parent_completion(self):
        self.data["nodes"][0]["children"] = ["S1"]
        self.data["nodes"] = self.data["nodes"][:4]
        plan = approved(self.data)
        self.assertFalse(plan.complete["root"])
        runtime = {"plan_digest": plan.digest, "nodes": {"S1.1": report("coordinator"), "S1.2": report("coordinator"), "S1": report("user")}}
        self.assertEqual(plan.frontier(runtime)["aggregate"], [{"task_id": "root", "task_completion_allowed": False}])
        self.assertIn("未选中：S2", plan.render())

    def test_partial_dependency_cannot_release_full_task_contract(self):
        self.data["nodes"][1]["children"] = ["S1.1"]
        self.data["nodes"] = [n for n in self.data["nodes"] if n["task_id"] != "S1.2"]
        self.data["nodes"][-1]["depends_on"] = ["S1"]
        with self.assertRaisesRegex(ValueError, "部分覆盖"):
            Plan(self.data)

    def test_dependency_cycle_including_serial_order_is_rejected(self):
        self.data["nodes"][2]["depends_on"] = ["S2.1"]
        with self.assertRaisesRegex(ValueError, "死锁"):
            Plan(self.data)

    def test_ancestor_dependency_deadlock_is_rejected(self):
        self.data["nodes"][2]["depends_on"] = ["S1"]
        with self.assertRaisesRegex(ValueError, "死锁"):
            Plan(self.data)

    def test_unknown_dependency_and_unexpanded_descendants_rejected(self):
        self.data["nodes"][2]["depends_on"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "未解析"):
            Plan(self.data)
        self.data = example()
        self.data["nodes"][2]["known_children"] = ["S1.1.1"]
        with self.assertRaisesRegex(ValueError, "未展开"):
            Plan(self.data)

    def test_external_unfinished_dependency_blocks_without_expanding_scope(self):
        self.data["nodes"][2]["depends_on"] = ["external"]
        self.data["external_dependencies"] = {"external": {"completed": False}}
        plan = approved(self.data)
        runtime = {"plan_digest": plan.digest, "nodes": {}}
        self.assertEqual(plan.frontier(runtime)["launch"], ["S1.2"])
        self.data["external_dependencies"]["external"] = {"completed": True, "basis": "现场核对输出"}
        plan = approved(self.data)
        self.assertIn("S1.1", plan.frontier({"plan_digest": plan.digest, "nodes": {}})["launch"])

    def test_review_and_authorization_gate(self):
        self.data.pop("review")
        self.plan = Plan(self.data)
        self.assertEqual(self.ready()["launch"], [])
        self.assertTrue(self.ready()["blocked"])

    def test_strategy_change_invalidates_old_review_and_runtime(self):
        old = self.plan.digest
        self.data["nodes"][2]["agent"] = "claude"
        self.plan = Plan(self.data)
        self.assertNotEqual(self.plan.digest, old)
        with self.assertRaisesRegex(ValueError, "摘要不匹配"):
            self.ready()
        self.runtime["plan_digest"] = self.plan.digest
        self.assertEqual(self.ready()["launch"], [])

    def test_progress_revision_does_not_invalidate_review(self):
        self.data["revision"] = 22
        self.data["runtime"] = {"anything": "dynamic"}
        self.assertEqual(Plan(self.data).digest, self.plan.digest)

    def test_running_unknown_and_failed_never_relaunch(self):
        for phase in ("launching", "running", "unknown", "failed"):
            self.runtime["nodes"] = {"S1.1": {"phase": phase}}
            self.assertEqual(self.ready()["launch"], ["S1.2"])

    def test_failure_does_not_release_serial_successor(self):
        self.accepted_backend()
        self.runtime["nodes"]["S1"] = {"phase": "reported", "outcome": "failed"}
        self.assertEqual(self.ready()["launch"], [])
        self.assertEqual(self.ready()["accept"], [])

    def test_wrong_acceptance_actor_missing_evidence_and_premature_parent_rejected(self):
        self.accepted_backend()
        self.runtime["nodes"]["S1"] = report("coordinator")
        with self.assertRaisesRegex(ValueError, "验收者"):
            self.ready()
        self.runtime["nodes"]["S1"] = report("user")
        self.runtime["nodes"]["S1"]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "证据"):
            self.ready()
        self.runtime["nodes"] = {"S1": report("user")}
        with self.assertRaisesRegex(ValueError, "尚未验收"):
            self.ready()

    def test_duplicate_or_disconnected_nodes_rejected(self):
        self.data["nodes"].append(copy.deepcopy(self.data["nodes"][2]))
        with self.assertRaisesRegex(ValueError, "重复 Task"):
            Plan(self.data)
        self.data = example()
        self.data["nodes"].append(node("orphan"))
        with self.assertRaisesRegex(ValueError, "未连到根"):
            Plan(self.data)

    def test_deep_inheritance(self):
        data = {"schema": 2, "plan_version": 1, "root_task": "r", "nodes": [node("r", ["a"], "parallel"), node("a", ["b"]), node("b", ["c"], "auto-sequential"), node("c", ["d"]), node("d")]}
        plan = approved(data)
        self.assertEqual(plan.mode["a"], "parallel")
        self.assertEqual(plan.mode["d"], "auto-sequential")
        self.assertEqual(plan.frontier({"plan_digest": plan.digest, "nodes": {}})["launch"], ["d"])

    def test_explicit_human_gate_in_parallel_and_no_manual_bypass(self):
        self.data["nodes"][2]["acceptance_actor"] = "user"
        self.plan = approved(self.data)
        self.runtime = {"plan_digest": self.plan.digest, "nodes": {"S1.1": report()}}
        self.assertEqual(self.ready()["accept"][0]["actor"], "user")
        self.data["nodes"][1]["acceptance_actor"] = "coordinator"
        with self.assertRaisesRegex(ValueError, "绕过"):
            Plan(self.data)

    def test_premature_running_and_report_without_evidence(self):
        self.runtime["nodes"] = {"S2.1": {"phase": "running"}}
        with self.assertRaisesRegex(ValueError, "调度门"):
            self.ready()
        self.runtime["nodes"] = {"S1.1": {"phase": "reported", "outcome": "succeeded"}}
        self.assertEqual(self.ready()["accept"], [])
        self.assertTrue(any("缺少证据" in x["reason"] for x in self.ready()["blocked"]))

    def test_example_asset_is_valid_and_pending_review_never_launches(self):
        asset = SCRIPT.parent.parent / "references/example-plan.json"
        plan = Plan(json.loads(asset.read_text()))
        ready = plan.frontier({"plan_digest": plan.digest, "nodes": {}})
        self.assertEqual(ready["launch"], [])
        self.assertIn("接口实现", plan.render())

    def test_cli_render_and_ready_use_same_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(self.data))
            state = Path(directory) / "state.json"
            state.write_text(json.dumps(self.runtime))
            rendered = subprocess.run([sys.executable, str(SCRIPT), "render", str(path)], text=True, capture_output=True, check=True).stdout
            self.assertIn(self.plan.digest, rendered)
            self.assertIn("验收串行", rendered)
            self.assertIn("协调汇总", rendered)
            self.assertIn("示例 · S1.1", rendered)
            ready = subprocess.run([sys.executable, str(SCRIPT), "ready", str(path), "--state", str(state)], text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(ready.stdout)["launch"], ["S1.1", "S1.2"])
            missing = subprocess.run([sys.executable, str(SCRIPT), "ready", str(path)], text=True, capture_output=True)
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
