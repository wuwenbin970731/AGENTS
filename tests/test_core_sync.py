from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/core-sync/scripts/core_sync.py"
spec = importlib.util.spec_from_file_location("core_sync", SCRIPT)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def command(*args, cwd=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def git(path, *args):
    return command("git", "-C", path, *args)


class CoreSyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin = self.root / "origin"
        self.origin.mkdir()
        for directory in ("scripts", "skills"):
            shutil.copytree(ROOT / directory, self.origin / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("AGENTS.md", "PROJECT_AGENTS.md", "GLOBAL_AGENTS.md", "README.md", "TASK_WORKFLOW.md", "TASK_TEMPLATE.md", "TASK_ITERATION_TEMPLATE.md"):
            shutil.copy2(ROOT / name, self.origin / name)
        (self.origin / ".tasks").mkdir()
        for name in ("config.json", ".gitignore"):
            shutil.copy2(ROOT / ".tasks" / name, self.origin / ".tasks" / name)
        git(self.origin, "init", "-q", "-b", "main")
        self.commit("baseline")
        self.old = git(self.origin, "rev-parse", "HEAD")
        self.checkout = self.root / "core"
        command("git", "clone", "-q", self.origin, self.checkout)
        self.a, self.b, self.control = [self.root / name for name in ("a", "b", "control")]
        for path in (self.a, self.b, self.control):
            self.install(path)
        source = self.origin / "PROJECT_AGENTS.md"
        source.write_text(source.read_text() + "\n## 新版 Core 规则\n\n新增验证要求。\n")
        self.commit("updated template")
        self.latest = git(self.origin, "rev-parse", "HEAD")
        self.config_path = self.root / "repos.json"
        self.registry = {"schema": 1, "core_checkout": str(self.checkout), "control_workspace": str(self.control),
                         "defaults": {"agent": "codex", "max_parallel": 2},
                         "global_targets": [{"id": "codex", "path": str(self.root / "user/AGENTS.md")}],
                         "repos": [{"id": "a", "path": str(self.a)}, {"id": "b", "path": str(self.b)}]}
        self.save_config()
        self.proposal = self.root / "proposal.md"
        self.proposal.write_text("逐章节审阅：采用新增规则，保留本地章节；验证 doctor、diff 和相关 Skill。\n")

    def commit(self, message):
        git(self.origin, "add", ".")
        git(self.origin, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", message)

    def install(self, folder):
        folder.mkdir()
        git(folder, "init", "-q")
        init = self.origin / "scripts/init_project.py"
        preview = json.loads(command(sys.executable, init, folder))
        command(sys.executable, init, folder, "--apply", "--approve-plan", preview["plan_digest"])

    def save_config(self):
        self.config_path.write_text(json.dumps(self.registry))
        return core.Config(self.config_path)

    def prepare(self, selected=None):
        record = core.prepare(self.save_config(), selected)
        self.batch_path = Path(record["batch"])
        self.batch = core.Batch(self.batch_path)
        return record

    def previews(self):
        self.batch.preview_global("codex")
        for key in self.batch.data["repos"]:
            if self.batch.data["repos"][key]["initial"]["status"] == "ready":
                result = self.batch.preview(key, self.proposal)
                self.assertEqual(result["status"], "ready", result)
        return self.batch.review()

    def approve(self, selection):
        review = self.previews()
        self.batch.approve(review["review_digest"], selection, "用户明确批准该具体提案")
        return review

    def test_prepare_pins_fetched_commit_creates_tasks_without_target_writes(self):
        before = (self.a / "AGENTS.md").read_bytes()
        record = self.prepare()
        self.assertEqual(record["source_commit"], self.latest)
        self.assertNotEqual(git(self.checkout, "rev-parse", "HEAD"), self.latest)
        self.assertEqual((self.a / "AGENTS.md").read_bytes(), before)
        self.assertFalse((self.root / "user/AGENTS.md").exists())
        self.assertEqual(git(self.batch.source, "status", "--porcelain"), "")
        tree = self.batch.render()
        self.assertIn("项目预览 [并行；最多 2", tree)
        self.assertIn("Core同步 · S1 · a", tree)
        parent = self.control / self.batch.data["task"]["path"]
        self.assertIn("orchestration/plan.json", parent.read_text())
        self.assertNotIn("<待补充", parent.read_text())
        strategy = json.loads((parent.parent / "orchestration/plan.json").read_text())
        planctl = self.batch.source / "skills/task-orchestration/scripts/planctl.py"
        checked = json.loads(command(sys.executable, planctl, "check", parent.parent / "orchestration/plan.json"))
        self.assertEqual(checked["节点数"], 3)
        self.assertEqual(strategy["nodes"][1]["workspace"], "registry:a")
        self.assertEqual(strategy["nodes"][1]["session_name"], strategy["nodes"][1]["terminal_title"])
        cli = self.control / ".tasks/bin/taskctl"
        self.assertEqual(json.loads(command(cli, "--root", self.control, "doctor"))["errors"], 0)

    def test_entry_is_cwd_independent_and_enabled_selection_is_explicit(self):
        self.registry["repos"][1]["enabled"] = False
        self.save_config()
        entry = ROOT / "scripts/core_sync.py"
        a = json.loads(command(sys.executable, entry, "inspect", "--config", self.config_path, cwd=self.a))
        b = json.loads(command(sys.executable, entry, "inspect", "--config", self.config_path, cwd=self.b))
        self.assertEqual(a, b)
        self.assertEqual([r["id"] for r in a["repos"]], ["a"])
        with self.assertRaisesRegex(ValueError, "禁用"):
            self.save_config().select(["b"])

    def test_duplicate_alias_path_and_relative_path_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.a, target_is_directory=True)
        self.registry["repos"][1]["path"] = str(alias)
        with self.assertRaisesRegex(ValueError, "重复"):
            self.save_config()
        self.registry["repos"][1]["path"] = "relative"
        with self.assertRaisesRegex(ValueError, "相对路径"):
            self.save_config()

    def test_blocked_repo_is_recorded_without_hiding_healthy_target(self):
        self.registry["repos"][1]["path"] = str(self.root / "missing")
        record = self.prepare()
        self.assertEqual([r["status"] for r in record["repos"]], ["ready", "blocked"])
        self.previews()
        review = self.batch.review()
        self.assertEqual(review["projects"]["b"]["status"], "blocked")
        self.batch.approve(review["review_digest"], {"projects": {"a": ["AGENTS.md"]}}, "明确批准 a")
        self.assertTrue(self.batch.gate_project("a")["apply_allowed"])

    def test_independent_manifest_bases_are_used(self):
        shutil.rmtree(self.b)
        self.install(self.b)
        self.prepare()
        self.previews()
        self.assertEqual(core.load(self.batch_path / "repos/a/preview.json")["base_commit"], self.old)
        second = core.load(self.batch_path / "repos/b/preview.json")
        self.assertEqual(second["base_commit"], self.latest)
        self.assertEqual(next(f for f in second["files"] if f["path"] == "AGENTS.md")["action"], "unchanged")

    def test_local_edits_conflict_and_override_are_preserved_during_preview(self):
        rules = self.a / "AGENTS.md"
        rules.write_text(rules.read_text() + "\n项目本地内容\n")
        (self.a / "AGENTS.override.md").write_text("本地 override")
        before = rules.read_bytes()
        self.prepare(["a"])
        preview = self.batch.preview("a", self.proposal)
        self.assertEqual(preview["status"], "ready", preview)
        self.assertEqual(next(f for f in preview["files"] if f["path"] == "AGENTS.md")["action"], "conflict")
        self.assertIn("AGENTS.override.md", preview["inputs"])
        self.assertEqual(rules.read_bytes(), before)

    def test_partial_approval_gate_and_manifest_guard(self):
        self.prepare()
        self.approve({"projects": {"a": ["AGENTS.md"]}})
        result = self.batch.gate_project("a")
        self.assertEqual(result["approved_files"], ["AGENTS.md"])
        self.assertTrue(result["manifest_advance_allowed"])
        with self.assertRaisesRegex(ValueError, "未获批准"):
            self.batch.gate_project("b")
        with self.assertRaisesRegex(ValueError, "未获批准"):
            self.batch.gate_global("codex")
        self.assertFalse((self.root / "user/AGENTS.md").exists())

    def test_partial_files_cannot_advance_manifest(self):
        target = self.origin / "TASK_TEMPLATE.md"
        target.write_text(target.read_text() + "\n额外模板更新\n")
        self.commit("second source change")
        self.prepare(["a"])
        self.approve({"projects": {"a": ["AGENTS.md"]}})
        self.assertFalse(self.batch.gate_project("a")["manifest_advance_allowed"])

    def test_wrong_digest_and_missing_semantic_proposal_cannot_approve(self):
        self.prepare(["a"])
        self.batch.preview_global("codex")
        self.batch.preview("a")
        with self.assertRaisesRegex(ValueError, "语义提案"):
            self.batch.review()
        self.batch.preview("a", self.proposal)
        with self.assertRaisesRegex(ValueError, "摘要"):
            self.batch.approve("wrong", {"projects": {"a": ["AGENTS.md"]}}, "批准")
        self.assertFalse((self.batch_path / "approval.json").exists())

    def test_reviewed_project_drift_including_mode_and_observed_file(self):
        self.prepare(["a"])
        self.approve({"projects": {"a": ["AGENTS.md"]}})
        target = self.a / "AGENTS.md"
        original = target.read_bytes()
        target.write_bytes(original + b"changed")
        with self.assertRaisesRegex(ValueError, "输入已变化"):
            self.batch.gate_project("a")
        target.write_bytes(original)
        target.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "输入已变化"):
            self.batch.gate_project("a")

    def test_changed_proposal_and_config_invalidate_old_approval(self):
        self.prepare(["a"])
        self.approve({"projects": {"a": ["AGENTS.md"]}})
        self.proposal.write_text("不同的合并决策")
        self.batch.preview("a", self.proposal)
        with self.assertRaisesRegex(ValueError, "旧批准失效"):
            self.batch.gate_project("a")
        self.registry["defaults"]["max_parallel"] = 4
        self.save_config()
        with self.assertRaisesRegex(ValueError, "配置"):
            core.Batch(self.batch_path)

    def test_global_must_match_approved_post_state_before_project_gate(self):
        self.prepare(["a"])
        self.approve({"projects": {"a": ["AGENTS.md"]}, "globals": ["codex"]})
        gate = self.batch.gate_global("codex")
        with self.assertRaises(OSError):
            self.batch.gate_project("a")
        target = self.root / "user/AGENTS.md"
        command(sys.executable, self.batch.source / "scripts/sync_global_agents.py", "--target", target,
                "--apply", "--approve-plan", gate["sync_plan_digest"])
        self.batch.record_global("codex")
        self.assertTrue(self.batch.gate_project("a")["apply_allowed"])
        target.write_text(target.read_text() + "drift")
        with self.assertRaisesRegex(ValueError, "漂移"):
            self.batch.gate_project("a")

    def test_duplicate_active_batches_rejected_until_explicit_close(self):
        self.prepare(["a"])
        with self.assertRaisesRegex(ValueError, "未关闭"):
            core.prepare(self.save_config(), ["a"])
        command(sys.executable, SCRIPT, "close", "--batch", self.batch_path, "--basis", "确认无活动 worker，结束测试批次")
        new = core.prepare(self.save_config(), ["a"])
        self.assertNotEqual(new["batch"], str(self.batch_path))
        with self.assertRaisesRegex(ValueError, "已关闭"):
            self.batch.approval()

    def test_snapshot_changes_and_cross_environment_are_rejected(self):
        self.prepare(["a"])
        path = self.batch.source / "README.md"
        original = path.read_bytes()
        path.write_bytes(original + b"dirty")
        with self.assertRaisesRegex(ValueError, "变脏"):
            core.Batch(self.batch_path)
        path.write_bytes(original)
        data = core.load(self.batch_path / "batch.json")
        data["environment"] = "different-environment"
        core.write(self.batch_path / "batch.json", data)
        with self.assertRaisesRegex(ValueError, "另一执行环境"):
            core.Batch(self.batch_path)

    def test_unreproducible_baseline_and_symlink_targets_block_preview(self):
        self.prepare(["a"])
        path = self.a / ".tasks/agent-core.json"
        manifest = json.loads(path.read_text())
        manifest["files"]["AGENTS.md"] = "0" * 64
        path.write_text(json.dumps(manifest))
        preview = self.batch.preview("a", self.proposal)
        self.assertEqual(preview["status"], "blocked")
        self.assertIn("无法重现", preview["reason"])
        manifest["files"]["AGENTS.md"] = core.sha((self.a / "AGENTS.md").read_bytes())
        path.write_text(json.dumps(manifest))
        target = self.a / "AGENTS.md"
        target.unlink()
        target.symlink_to(self.origin / "AGENTS.md")
        self.assertEqual(self.batch.preview("a", self.proposal)["status"], "blocked")

    def test_new_skills_installed_and_no_core_task_instances_copied(self):
        for name in ("core-sync", "task-orchestration"):
            directory = self.a / ".agents/skills" / name
            self.assertTrue((directory / "SKILL.md").exists())
        self.assertTrue((self.a / ".agents/skills/core-sync/scripts/core_sync.py").exists())
        self.assertEqual(list((self.a / ".tasks").glob("*/**/TASK.md")), [])
        manifest = json.loads((self.a / ".tasks/agent-core.json").read_text())
        self.assertIn(".agents/skills/task-orchestration/references/descendants.md", manifest["files"])
        for asset in ("scripts/sessionctl.py", "references/session-naming.md"):
            self.assertIn(".agents/skills/task-orchestration/" + asset, manifest["files"])
            self.assertTrue((self.a / ".agents/skills/task-orchestration" / asset).exists())
        self.assertTrue((self.a / ".tasks/bin/taskctl").stat().st_mode & 0o111)

    def test_success_record_checks_manifest_and_actual_install(self):
        self.prepare(["a"])
        self.approve({"projects": {"a": ["AGENTS.md"]}})
        result = {"outcome": "updated", "evidence": ["测试记录"], "checks": [{"command": "taskctl doctor", "returncode": 0}]}
        with self.assertRaisesRegex(ValueError, "安装清单"):
            self.batch.record_project("a", result)
        shutil.copyfile(self.batch.source / "PROJECT_AGENTS.md", self.a / "AGENTS.md")
        installed_manifest = command(sys.executable, "-c", "import runpy; print(runpy.run_path('scripts/init_project.py')['manifest_content']())", cwd=self.batch.source)
        (self.a / ".tasks/agent-core.json").write_text(installed_manifest + "\n")
        doctor = json.loads(command(self.a / ".tasks/bin/taskctl", "--root", self.a, "doctor"))
        self.assertEqual(doctor["errors"], 0)
        self.assertEqual(self.batch.record_project("a", result)["result"]["outcome"], "updated")
        (self.a / "AGENTS.md").unlink()
        with self.assertRaisesRegex(ValueError, "缺失"):
            self.batch.record_project("a", result)

    def test_runtime_overrides_do_not_rewrite_registry(self):
        before = self.config_path.read_bytes()
        record = core.prepare(self.save_config(), ["a"], agent="claude", max_parallel=1)
        batch = core.Batch(record["batch"])
        self.assertEqual(batch.data["agent"], "claude")
        self.assertEqual(batch.data["max_parallel"], 1)
        self.assertEqual(self.config_path.read_bytes(), before)

    def test_disjoint_projects_still_serialize_shared_global_target(self):
        self.prepare(["a"])
        with self.assertRaisesRegex(ValueError, "未关闭"):
            core.prepare(self.save_config(), ["b"])

    def test_observed_inputs_and_unknown_approval_paths_are_checked(self):
        watched = self.a / "settings.json"
        watched.write_text("{}")
        self.prepare(["a"])
        self.batch.preview_global("codex")
        self.batch.preview("a", self.proposal, ["settings.json"])
        review = self.batch.review()
        with self.assertRaisesRegex(ValueError, "未预览"):
            self.batch.approve(review["review_digest"], {"projects": {"a": ["settings.json"]}}, "批准")
        self.batch.approve(review["review_digest"], {"projects": {"a": ["AGENTS.md"]}}, "批准")
        watched.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, "输入已变化"):
            self.batch.gate_project("a")

    def test_fetch_failure_does_not_use_existing_tracking_ref(self):
        git(self.checkout, "remote", "set-url", "origin", str(self.root / "unavailable"))
        with self.assertRaisesRegex(ValueError, "不回退缓存"):
            core.prepare(self.save_config(), ["a"])
        state_root = self.control / ".tasks/.state/core-sync"
        self.assertEqual(list(state_root.glob("*/batch.json")), [])
        self.assertFalse((state_root / "prepare.lock").exists())

    def test_malformed_manifest_does_not_hide_other_repos(self):
        path = self.b / ".tasks/agent-core.json"
        data = json.loads(path.read_text())
        data["source_commit"] = 123
        path.write_text(json.dumps(data))
        report = core.inspect(self.save_config())
        self.assertEqual([r["status"] for r in report["repos"]], ["ready", "blocked"])

    def test_readonly_global_conflict_is_reported_and_projects_can_be_approved(self):
        target = self.root / "user/AGENTS.md"
        target.parent.mkdir()
        target.write_text("未知旧规则，不应覆盖")
        self.prepare(["a"])
        self.approve({"projects": {"a": ["AGENTS.md"]}})
        self.assertEqual(self.batch.review()["globals"]["codex"]["status"], "blocked")
        self.assertTrue(self.batch.gate_project("a")["apply_allowed"])
        self.assertEqual(target.read_text(), "未知旧规则，不应覆盖")
        self.assertIn("本轮具体更新提案", self.batch.render_review())


class CoreSyncParserTest(unittest.TestCase):
    def test_dynamic_copy_map_extensions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            script = root / "scripts/init_project.py"
            script.write_text('COPY_MAP = [(SOURCE_ROOT / "a", Path("b"))]\n')
            self.assertEqual(core.copy_map(root), {"b": "a"})
            script.write_text(script.read_text() + 'COPY_MAP.append((SOURCE_ROOT / "c", Path("d")))\n')
            with self.assertRaisesRegex(ValueError, "动态顶层"):
                core.copy_map(root)


if __name__ == "__main__":
    unittest.main()
