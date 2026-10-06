#!/usr/bin/env python3
"""Plan or apply a safe first-time installation into a project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SOURCE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_MARKER = "wuwenbin970731/AGENTS"
MANIFEST_PATH = Path(".tasks/agent-core.json")
COPY_MAP = [
    (SOURCE_ROOT / "PROJECT_AGENTS.md", Path("AGENTS.md")),
    (SOURCE_ROOT / ".tasks/config.json", Path(".tasks/config.json")),
    (SOURCE_ROOT / ".tasks/.gitignore", Path(".tasks/.gitignore")),
    (SOURCE_ROOT / "TASK_WORKFLOW.md", Path(".tasks/TASK_WORKFLOW.md")),
    (SOURCE_ROOT / "TASK_TEMPLATE.md", Path(".tasks/TASK_TEMPLATE.md")),
    (SOURCE_ROOT / "TASK_ITERATION_TEMPLATE.md", Path(".tasks/TASK_ITERATION_TEMPLATE.md")),
    (SOURCE_ROOT / "skills/task-runtime/scripts/taskctl.py", Path(".tasks/bin/taskctl")),
    (SOURCE_ROOT / "skills/task-runtime/SKILL.md", Path(".agents/skills/task-runtime/SKILL.md")),
    (SOURCE_ROOT / "skills/task-runtime/agents/openai.yaml", Path(".agents/skills/task-runtime/agents/openai.yaml")),
    (SOURCE_ROOT / "skills/task-runtime/references/protocol.md", Path(".agents/skills/task-runtime/references/protocol.md")),
    (SOURCE_ROOT / "skills/task-runtime/references/schema-v4.md", Path(".agents/skills/task-runtime/references/schema-v4.md")),
    (SOURCE_ROOT / "skills/task-runtime/references/schema-v5.md", Path(".agents/skills/task-runtime/references/schema-v5.md")),
    (SOURCE_ROOT / "skills/task-runtime/scripts/taskctl.py", Path(".agents/skills/task-runtime/scripts/taskctl.py")),
]


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        mode = 0o755 if source.name == "taskctl.py" else 0o644
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def path_state(path: Path) -> dict[str, str]:
    if path.is_symlink():
        return {"type": "symlink", "target": os.readlink(path)}
    if not path.exists():
        return {"type": "missing"}
    if path.is_file():
        return {"type": "file", "sha256": sha256(path)}
    if path.is_dir():
        return {"type": "directory"}
    return {"type": "other"}


def digest_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def git_output(*arguments: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(SOURCE_ROOT), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def manifest_content() -> str:
    remote = git_output("remote", "get-url", "origin")
    commit = git_output("rev-parse", "HEAD")
    dirty_output = git_output("status", "--porcelain")
    payload = {
        "schema": 1,
        "source": remote or str(SOURCE_ROOT),
        "source_commit": commit,
        "source_dirty": dirty_output is None or bool(dirty_output),
        "files": {str(relative): sha256(source) for source, relative in COPY_MAP},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def existing_tasks_owned(target: Path) -> bool:
    tasks = target / ".tasks"
    if not tasks.exists():
        return True
    if not tasks.is_dir():
        return False
    marker = tasks / "config.json"
    if not marker.exists():
        return not any(tasks.iterdir())
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("managed_by") == CONFIG_MARKER
    except (OSError, json.JSONDecodeError):
        return False


def plan(target: Path) -> tuple[list[dict[str, str]], bool, str]:
    actions: list[dict[str, str]] = []
    conflict = False
    if not existing_tasks_owned(target):
        actions.append({"action": "conflict", "path": str(target / '.tasks'), "reason": "existing .tasks is not empty and is not managed by this repository"})
        conflict = True
    for source, relative in COPY_MAP:
        destination = target / relative
        if not destination.exists():
            actions.append({"action": "create", "path": str(relative), "source": str(source.relative_to(SOURCE_ROOT))})
        elif destination.is_file() and destination.read_bytes() == source.read_bytes():
            actions.append({"action": "unchanged", "path": str(relative)})
        else:
            actions.append({"action": "conflict", "path": str(relative), "reason": "destination exists with different content"})
            conflict = True
    manifest = target / MANIFEST_PATH
    desired_manifest = manifest_content().encode("utf-8")
    if not manifest.exists():
        actions.append({"action": "create", "path": str(MANIFEST_PATH), "source": "generated install manifest"})
    elif manifest.is_file() and manifest.read_bytes() == desired_manifest:
        actions.append({"action": "unchanged", "path": str(MANIFEST_PATH)})
    else:
        actions.append({"action": "refresh", "path": str(MANIFEST_PATH), "source": "generated install manifest"})
    plan_basis: dict[str, object] = {
        "schema": 1,
        "operation": "initialize-project",
        "project": str(target),
        "tasks_owned": existing_tasks_owned(target),
        "actions": actions,
        "source_files": {str(relative): sha256(source) for source, relative in COPY_MAP},
        "destination_states": {
            str(relative): path_state(target / relative) for _source, relative in COPY_MAP
        },
        "manifest_source_sha256": sha256_bytes(desired_manifest),
        "manifest_destination_state": path_state(manifest),
    }
    return actions, conflict, digest_payload(plan_basis)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create missing files only with the reviewed --approve-plan digest",
    )
    parser.add_argument(
        "--approve-plan",
        metavar="SHA256",
        help="apply only the exact plan digest that the user reviewed",
    )
    args = parser.parse_args()
    target = args.project.expanduser().resolve()
    if not target.is_dir():
        print(json.dumps({"error": f"project directory does not exist: {target}"}), file=sys.stderr)
        return 2
    actions, conflict, plan_digest = plan(target)
    print(
        json.dumps(
            {
                "project": str(target),
                "apply": args.apply,
                "actions": actions,
                "plan_digest": plan_digest,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if conflict:
        print("Initialization stopped: resolve conflicts through the documented semantic merge workflow.", file=sys.stderr)
        return 3
    if not args.apply:
        return 0
    if args.approve_plan != plan_digest:
        print(
            "Application stopped: run dry-run, review it, and pass its exact plan_digest with --approve-plan.",
            file=sys.stderr,
        )
        return 3
    try:
        for source, relative in COPY_MAP:
            destination = target / relative
            if not destination.exists():
                atomic_copy(source, destination)
        manifest = target / MANIFEST_PATH
        manifest.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{manifest.name}.", dir=manifest.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(manifest_content())
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, manifest)
        finally:
            temporary.unlink(missing_ok=True)
    except OSError as error:
        print(json.dumps({"error": f"initialization failed: {error}"}), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
