from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
INIT = REPO_ROOT / "scripts/init_project.py"
SOURCE_TASKCTL = REPO_ROOT / "skills/task-runtime/scripts/taskctl.py"
SYNC_GLOBAL = REPO_ROOT / "scripts/sync_global_agents.py"


class TaskRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_command(self, *command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self.project,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )

    def initialize(self) -> None:
        preview = self.run_command(sys.executable, str(INIT), str(self.project))
        plan_digest = json.loads(preview.stdout)["plan_digest"]
        result = self.run_command(
            sys.executable,
            str(INIT),
            str(self.project),
            "--apply",
            "--approve-plan",
            plan_digest,
        )
        self.assertEqual(json.loads(result.stdout)["apply"], True)

    def taskctl(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run_command(str(self.project / ".tasks/bin/taskctl"), *arguments, check=check)

    def create_task(self, title: str = "Progressive task", slug: str = "progressive-task") -> dict[str, object]:
        result = self.taskctl(
            "new",
            title,
            "--summary",
            "Verify metadata-only discovery and explicit context loading",
            "--slug",
            slug,
            "--mode",
            "rigorous",
            "--tag",
            "task-system",
        )
        return json.loads(result.stdout)

    def test_initializer_plans_before_apply_and_is_idempotent(self) -> None:
        preview = self.run_command(sys.executable, str(INIT), str(self.project))
        plan = json.loads(preview.stdout)
        self.assertFalse(plan["apply"])
        self.assertFalse((self.project / ".tasks").exists())
        self.assertTrue(any(item["path"] == ".tasks/bin/taskctl" for item in plan["actions"]))

        self.initialize()
        self.assertTrue((self.project / ".tasks/bin/taskctl").exists())
        self.assertTrue((self.project / ".agents/skills/task-runtime/SKILL.md").exists())
        manifest = json.loads((self.project / ".tasks/agent-core.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], 1)
        self.assertIn(".tasks/bin/taskctl", manifest["files"])
        second_preview = json.loads(
            self.run_command(sys.executable, str(INIT), str(self.project)).stdout
        )
        second = self.run_command(
            sys.executable,
            str(INIT),
            str(self.project),
            "--apply",
            "--approve-plan",
            second_preview["plan_digest"],
        )
        self.assertTrue(all(item["action"] == "unchanged" for item in json.loads(second.stdout)["actions"]))

    def test_initializer_requires_reviewed_plan_digest(self) -> None:
        preview = json.loads(
            self.run_command(sys.executable, str(INIT), str(self.project)).stdout
        )
        missing = self.run_command(
            sys.executable, str(INIT), str(self.project), "--apply", check=False
        )
        self.assertEqual(missing.returncode, 3)
        self.assertFalse((self.project / "AGENTS.md").exists())
        wrong = self.run_command(
            sys.executable,
            str(INIT),
            str(self.project),
            "--apply",
            "--approve-plan",
            "0" * 64,
            check=False,
        )
        self.assertEqual(wrong.returncode, 3)
        self.assertNotEqual(preview["plan_digest"], "0" * 64)
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_initializer_rejects_plan_after_target_changes(self) -> None:
        preview = json.loads(
            self.run_command(sys.executable, str(INIT), str(self.project)).stdout
        )
        (self.project / "AGENTS.md").write_bytes(
            (REPO_ROOT / "PROJECT_AGENTS.md").read_bytes()
        )
        stale = self.run_command(
            sys.executable,
            str(INIT),
            str(self.project),
            "--apply",
            "--approve-plan",
            str(preview["plan_digest"]),
            check=False,
        )
        self.assertEqual(stale.returncode, 3)
        self.assertIn("exact plan_digest", stale.stderr)
        self.assertFalse((self.project / ".tasks").exists())

    def test_initializer_refuses_unmanaged_tasks_directory(self) -> None:
        tasks = self.project / ".tasks"
        tasks.mkdir()
        (tasks / "business.txt").write_text("owned by project\n", encoding="utf-8")
        result = self.run_command(sys.executable, str(INIT), str(self.project), "--apply", check=False)
        self.assertEqual(result.returncode, 3)
        self.assertIn("not managed", result.stdout)
        self.assertFalse((self.project / "AGENTS.md").exists())
        direct = self.run_command(
            sys.executable,
            str(SOURCE_TASKCTL),
            "--root",
            str(self.project),
            "search",
            check=False,
        )
        self.assertEqual(direct.returncode, 2)
        self.assertIn("managed task runtime not found", direct.stderr)

    def test_search_reads_metadata_without_disclosing_body(self) -> None:
        self.initialize()
        meta = self.create_task()
        task_path = self.project / str(meta["path"])
        task_path.write_text(task_path.read_text(encoding="utf-8") + "\nBODY_ONLY_SECRET_7391\n", encoding="utf-8")

        search = self.taskctl("search", "task-system")
        self.assertNotIn("BODY_ONLY_SECRET_7391", search.stdout)
        rows = json.loads(search.stdout)
        self.assertEqual(rows[0]["id"], meta["id"])
        self.assertNotIn("body", rows[0])
        entry = self.taskctl("show", str(meta["id"]), "--entry")
        self.assertIn("BODY_ONLY_SECRET_7391", entry.stdout)

    def test_context_requires_explicit_declaration_and_blocks_escape(self) -> None:
        self.initialize()
        meta = self.create_task()
        task_path = self.project / str(meta["path"])
        design = task_path.parent / "design/CURRENT.md"
        design.parent.mkdir()
        design.write_text("VISIBLE_DESIGN\n", encoding="utf-8")
        secret = task_path.parent.parent / "outside.md"
        secret.write_text("OUTSIDE_SECRET\n", encoding="utf-8")
        text = task_path.read_text(encoding="utf-8")
        text = text.replace(
            "|---|---|---|\n\n## 依赖契约",
            "|---|---|---|\n| `design/CURRENT.md` | Current design | Implementing the runtime |\n\n## 依赖契约",
        )
        task_path.write_text(text, encoding="utf-8")

        listed = json.loads(self.taskctl("context", "list", str(meta["id"])).stdout)
        self.assertEqual(listed[0]["resource"], "design/CURRENT.md")
        read = self.taskctl("context", "read", str(meta["id"]), "design/CURRENT.md")
        self.assertEqual(read.stdout, "VISIBLE_DESIGN\n")
        rejected = self.taskctl("context", "read", str(meta["id"]), "../outside.md", check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertNotIn("OUTSIDE_SECRET", rejected.stdout + rejected.stderr)

    def test_revision_conflict_prevents_lost_update(self) -> None:
        self.initialize()
        meta = self.create_task()
        task_id = str(meta["id"])
        updated = self.taskctl(
            "update",
            task_id,
            "--expect-revision",
            "1",
            "--checkpoint",
            "first writer",
        )
        self.assertEqual(json.loads(updated.stdout)["revision"], 2)
        conflict = self.taskctl(
            "update",
            task_id,
            "--expect-revision",
            "1",
            "--checkpoint",
            "stale writer",
            check=False,
        )
        self.assertEqual(conflict.returncode, 3)
        current = json.loads(self.taskctl("show", task_id).stdout)
        self.assertEqual(current["checkpoint"], "first writer")

    def test_session_binding_is_git_private_and_reports_staleness(self) -> None:
        self.initialize()
        meta = self.create_task()
        task_id = str(meta["id"])
        self.taskctl("bind", task_id, "--session", "session-A")
        git_dir = Path(self.run_command("git", "rev-parse", "--absolute-git-dir").stdout.strip())
        self.assertTrue((git_dir / "task-state/sessions/session-A.json").exists())
        current = json.loads(self.taskctl("current", "--session", "session-A").stdout)
        self.assertFalse(current["stale"])
        self.taskctl("update", task_id, "--expect-revision", "1", "--checkpoint", "changed")
        stale = json.loads(self.taskctl("current", "--session", "session-A").stdout)
        self.assertTrue(stale["stale"])
        self.taskctl(
            "update",
            task_id,
            "--expect-revision",
            "2",
            "--checkpoint",
            "session refreshed",
            "--session",
            "session-A",
        )
        refreshed = json.loads(self.taskctl("current", "--session", "session-A").stdout)
        self.assertFalse(refreshed["stale"])
        self.assertEqual(refreshed["seen_revision"], 3)

    def test_non_git_project_uses_ignored_state_fallback(self) -> None:
        non_git = Path(self.temporary.name) / "non-git"
        non_git.mkdir()
        preview = subprocess.run(
            [sys.executable, str(INIT), str(non_git)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        plan_digest = json.loads(preview.stdout)["plan_digest"]
        subprocess.run(
            [
                sys.executable,
                str(INIT),
                str(non_git),
                "--apply",
                "--approve-plan",
                plan_digest,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        runtime = non_git / ".tasks/bin/taskctl"
        created = subprocess.run(
            [str(runtime), "new", "Non git task", "--summary", "Test local state fallback"],
            cwd=non_git,
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        task_id = json.loads(created.stdout)["id"]
        subprocess.run(
            [str(runtime), "bind", str(task_id), "--session", "fallback-session"],
            cwd=non_git,
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertTrue((non_git / ".tasks/.state/sessions/fallback-session.json").exists())

    def test_doctor_accepts_valid_task(self) -> None:
        self.initialize()
        self.create_task()
        report = json.loads(self.taskctl("doctor").stdout)
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["tasks"], 1)
        self.assertEqual(report["warnings"], 0)

    def test_search_limit_and_legacy_schema_compatibility(self) -> None:
        self.initialize()
        for index in range(10):
            self.create_task(title=f"Shared goal {index}", slug=f"shared-goal-{index}")
        rows = json.loads(self.taskctl("search", "shared goal", "--limit", "100").stdout)
        self.assertEqual(len(rows), 8)

        legacy_dir = self.project / ".tasks/2025-01-01/legacy-task"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "TASK.md").write_text(
            "---\ntask_schema: 3\nid: legacy-task\nstatus: in_progress\nactive_iteration: iterations/F001.md\n---\n\n# Legacy searchable title\n",
            encoding="utf-8",
        )
        legacy = json.loads(self.taskctl("search", "legacy-task").stdout)
        self.assertEqual(legacy[0]["id"], "legacy-task")
        self.assertNotIn("active_iteration", legacy[0])

    def test_full_entry_write_checks_revision(self) -> None:
        self.initialize()
        meta = self.create_task()
        task_id = str(meta["id"])
        original = self.project / str(meta["path"])
        proposed = self.project / "proposed.md"
        proposed.write_text(
            original.read_text(encoding="utf-8").replace("当前正在解决：任务初始化。", "当前正在解决：实现完整写入。"),
            encoding="utf-8",
        )
        written = json.loads(
            self.taskctl("write", task_id, "--from", str(proposed), "--expect-revision", "1").stdout
        )
        self.assertEqual(written["revision"], 2)
        self.assertIn("实现完整写入", self.taskctl("show", task_id, "--entry").stdout)
        conflict = self.taskctl(
            "write", task_id, "--from", str(proposed), "--expect-revision", "1", check=False
        )
        self.assertEqual(conflict.returncode, 3)

    def test_repository_templates_stay_synchronized(self) -> None:
        for name in ("TASK_WORKFLOW.md", "TASK_TEMPLATE.md", "TASK_ITERATION_TEMPLATE.md"):
            self.assertEqual(
                (REPO_ROOT / name).read_bytes(),
                (REPO_ROOT / ".tasks" / name).read_bytes(),
                name,
            )

    def test_readme_requires_combined_review_before_apply(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("同时执行两个 dry-run", readme)
        self.assertIn("即使两边都无冲突，也必须停止并等待我明确确认", readme)
        self.assertIn("--approve-plan <global-digest>", readme)
        self.assertIn("--approve-plan <project-digest>", readme)
        self.assertGreaterEqual(
            readme.count("AGENTS Core：https://github.com/wuwenbin970731/AGENTS.git"),
            2,
        )
        self.assertNotIn("<AGENTS_CORE", readme)
        self.assertNotIn("AGENTS_CORE 本地路径或 Git URL", readme)

    def test_source_cli_compiles_and_reports_version(self) -> None:
        result = self.run_command(sys.executable, str(SOURCE_TASKCTL), "--version")
        self.assertRegex(result.stdout, r"taskctl \d+\.\d+\.\d+")

    def test_new_and_update_reject_multiline_metadata(self) -> None:
        self.initialize()
        rejected_new = self.taskctl(
            "new",
            "bad\ntitle",
            "--summary",
            "summary",
            "--slug",
            "bad-title",
            check=False,
        )
        self.assertEqual(rejected_new.returncode, 2)
        meta = self.create_task()
        rejected_update = self.taskctl(
            "update",
            str(meta["id"]),
            "--expect-revision",
            "1",
            "--checkpoint",
            "bad\ncheckpoint",
            check=False,
        )
        self.assertEqual(rejected_update.returncode, 2)
        self.assertEqual(json.loads(self.taskctl("show", str(meta["id"])).stdout)["revision"], 1)


class GlobalAgentsSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.target = Path(self.temporary.name) / "client/AGENTS.md"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_sync(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SYNC_GLOBAL),
                "--target",
                str(self.target),
                "--allow-dirty-source",
                *arguments,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )

    def apply_sync(self, *arguments: str) -> dict[str, object]:
        preview = json.loads(self.run_sync(*arguments).stdout)
        applied = self.run_sync(
            *arguments,
            "--apply",
            "--approve-plan",
            str(preview["plan_digest"]),
        )
        return json.loads(applied.stdout)

    def test_global_sync_plans_then_creates_managed_block(self) -> None:
        preview = json.loads(self.run_sync().stdout)
        self.assertEqual(preview["action"], "create")
        self.assertFalse(self.target.exists())
        applied = self.apply_sync()
        self.assertEqual(applied["action"], "create")
        content = self.target.read_text(encoding="utf-8")
        self.assertIn("<!-- agents-core-managed:", content)
        self.assertIn("<!-- /agents-core-managed -->", content)
        self.assertIn((REPO_ROOT / "GLOBAL_AGENTS.md").read_text(encoding="utf-8"), content)

    def test_global_sync_preserves_content_outside_managed_block(self) -> None:
        self.apply_sync()
        with self.target.open("a", encoding="utf-8") as handle:
            handle.write("\n# Local rules\n\nkeep me\n")
        result = self.apply_sync()
        self.assertEqual(result["action"], "unchanged")
        self.assertIn("# Local rules\n\nkeep me", self.target.read_text(encoding="utf-8"))

    def test_global_sync_rejects_edits_inside_managed_block(self) -> None:
        self.apply_sync()
        content = self.target.read_text(encoding="utf-8")
        self.target.write_text(content.replace("# Global Working Agreements", "# Edited Managed Rules"), encoding="utf-8")
        rejected = self.run_sync("--apply", "--approve-plan", "0" * 64, check=False)
        self.assertEqual(rejected.returncode, 3)
        self.assertIn("edited after installation", rejected.stdout)

    def test_global_sync_requires_explicit_legacy_boundary(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text(
            "# Old template\n\nold body\n\n# Local rules\n\nkeep me\n\n"
            "<!-- agents-template-sync\nsource: example\n-->\n",
            encoding="utf-8",
        )
        rejected = self.run_sync("--apply", check=False)
        self.assertEqual(rejected.returncode, 3)
        migrated = self.apply_sync("--adopt-local-tail-from", "# Local rules")
        self.assertEqual(migrated["action"], "migrate")
        content = self.target.read_text(encoding="utf-8")
        self.assertNotIn("# Old template", content)
        self.assertNotIn("agents-template-sync", content)
        self.assertTrue(content.endswith("# Local rules\n\nkeep me\n\n"))
        self.assertTrue(Path(str(migrated["backup"])).exists())

    def test_global_sync_requires_reviewed_plan_digest(self) -> None:
        preview = json.loads(self.run_sync().stdout)
        missing = self.run_sync("--apply", check=False)
        self.assertEqual(missing.returncode, 3)
        self.assertFalse(self.target.exists())
        wrong = self.run_sync(
            "--apply", "--approve-plan", "0" * 64, check=False
        )
        self.assertEqual(wrong.returncode, 3)
        self.assertNotEqual(preview["plan_digest"], "0" * 64)
        self.assertFalse(self.target.exists())

    def test_global_sync_rejects_plan_after_target_changes(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text(
            "# Old template\n\n# Local rules\n\nkeep me\n\n"
            "<!-- agents-template-sync\nsource: example\n-->\n",
            encoding="utf-8",
        )
        arguments = ("--adopt-local-tail-from", "# Local rules")
        preview = json.loads(self.run_sync(*arguments).stdout)
        self.target.write_text(
            self.target.read_text(encoding="utf-8").replace(
                "keep me\n\n<!--", "keep me\nchanged after review\n\n<!--"
            ),
            encoding="utf-8",
        )
        stale = self.run_sync(
            *arguments,
            "--apply",
            "--approve-plan",
            str(preview["plan_digest"]),
            check=False,
        )
        self.assertEqual(stale.returncode, 3)
        self.assertIn("exact plan_digest", stale.stderr)
        self.assertIn("# Old template", self.target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
