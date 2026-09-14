#!/usr/bin/env python3
"""Safely install or refresh the user-level AGENTS.md managed block."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


SOURCE_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = SOURCE_ROOT / "GLOBAL_AGENTS.md"
BEGIN_PREFIX = "<!-- agents-core-managed: "
BEGIN_SUFFIX = " -->"
END_MARKER = "<!-- /agents-core-managed -->"
LEGACY_MARKER = re.compile(r"<!-- agents-template-sync\n.*?\n-->\s*\Z", re.DOTALL)


class SyncConflict(RuntimeError):
    pass


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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


def source_metadata(source: bytes) -> dict[str, object]:
    remote = git_output("remote", "get-url", "origin")
    commit = git_output("rev-parse", "HEAD")
    dirty_output = git_output("status", "--porcelain")
    return {
        "schema": 1,
        "source": remote or str(SOURCE_ROOT),
        "source_path": str(SOURCE_PATH.relative_to(SOURCE_ROOT)),
        "source_commit": commit,
        "source_dirty": dirty_output is None or bool(dirty_output),
        "content_sha256": sha256_bytes(source),
    }


def managed_block(source: bytes, metadata: dict[str, object]) -> bytes:
    header = BEGIN_PREFIX + json.dumps(metadata, ensure_ascii=False, sort_keys=True) + BEGIN_SUFFIX + "\n"
    return header.encode("utf-8") + source + END_MARKER.encode("utf-8")


def parse_managed(content: bytes) -> tuple[bytes, bytes, bytes, dict[str, object]] | None:
    start = content.find(BEGIN_PREFIX.encode("utf-8"))
    if start < 0:
        return None
    if content.find(BEGIN_PREFIX.encode("utf-8"), start + 1) >= 0:
        raise SyncConflict("multiple agents-core managed blocks found")
    header_end = content.find((BEGIN_SUFFIX + "\n").encode("utf-8"), start)
    if header_end < 0:
        raise SyncConflict("managed block header is malformed")
    metadata_start = start + len(BEGIN_PREFIX.encode("utf-8"))
    metadata_bytes = content[metadata_start:header_end]
    body_start = header_end + len((BEGIN_SUFFIX + "\n").encode("utf-8"))
    end = content.find(END_MARKER.encode("utf-8"), body_start)
    if end < 0:
        raise SyncConflict("managed block end marker is missing")
    if content.find(END_MARKER.encode("utf-8"), end + 1) >= 0:
        raise SyncConflict("multiple agents-core end markers found")
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncConflict(f"managed block metadata is invalid: {error}") from error
    if not isinstance(metadata, dict):
        raise SyncConflict("managed block metadata must be an object")
    body = content[body_start:end]
    recorded_hash = metadata.get("content_sha256")
    if not isinstance(recorded_hash, str) or recorded_hash != sha256_bytes(body):
        raise SyncConflict("managed block was edited after installation; use a semantic merge instead of overwriting it")
    suffix_start = end + len(END_MARKER.encode("utf-8"))
    return content[:start], body, content[suffix_start:], metadata


def local_tail(content: bytes, heading: str) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SyncConflict("existing AGENTS.md is not UTF-8") from error
    legacy_marker = LEGACY_MARKER.search(text)
    content_end = legacy_marker.start() if legacy_marker else len(text)
    local_section = text[:content_end]
    matches = list(re.finditer(rf"(?m)^{re.escape(heading)}[ \t]*$", local_section))
    if len(matches) != 1:
        raise SyncConflict(f"local tail heading must occur exactly once: {heading!r}")
    return local_section[matches[0].start():].encode("utf-8")


def desired_content(
    current: bytes | None,
    source: bytes,
    metadata: dict[str, object],
    adopt_local_tail_from: str | None,
) -> tuple[bytes, str, dict[str, object]]:
    block = managed_block(source, metadata)
    details: dict[str, object] = {}
    if current is None:
        return block + b"\n", "create", details
    parsed = parse_managed(current)
    if parsed is not None:
        prefix, _old_body, suffix, old_metadata = parsed
        details["previous_source_commit"] = old_metadata.get("source_commit")
        desired = prefix + block + suffix
        return desired, "unchanged" if desired == current else "update", details
    if adopt_local_tail_from is None:
        raise SyncConflict(
            "existing AGENTS.md is not managed; review it and use --adopt-local-tail-from with an exact heading"
        )
    tail = local_tail(current, adopt_local_tail_from)
    details["preserved_local_tail"] = adopt_local_tail_from
    details["preserved_local_bytes"] = len(tail)
    return block + b"\n\n" + tail, "migrate", details


def default_target() -> Path:
    configured = os.environ.get("CODEX_HOME")
    root = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return root / "AGENTS.md"


def backup(current: bytes, target: Path) -> Path:
    directory = target.parent / ".agents-core-backups"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = directory / f"{target.name}.{stamp}.bak"
    destination.write_bytes(current)
    os.chmod(destination, 0o600)
    return destination


def atomic_write(target: Path, content: bytes, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=default_target())
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the managed block only with the reviewed --approve-plan digest",
    )
    parser.add_argument(
        "--approve-plan",
        metavar="SHA256",
        help="apply only the exact plan digest that the user reviewed",
    )
    parser.add_argument(
        "--allow-dirty-source",
        action="store_true",
        help="allow installing an uncommitted Core source, recording its exact content hash",
    )
    parser.add_argument(
        "--adopt-local-tail-from",
        metavar="HEADING",
        help="one-time migration: replace the legacy prefix and preserve content from this exact heading",
    )
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    source = SOURCE_PATH.read_bytes()
    metadata = source_metadata(source)
    if args.apply and metadata["source_dirty"] and not args.allow_dirty_source:
        print(
            json.dumps(
                {"error": "Core working tree is dirty; commit it first or explicitly use --allow-dirty-source"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3
    try:
        current = target.read_bytes() if target.exists() else None
        if target.exists() and not target.is_file():
            raise SyncConflict("target exists and is not a regular file")
        desired, action, details = desired_content(
            current, source, metadata, args.adopt_local_tail_from
        )
    except (OSError, SyncConflict) as error:
        print(
            json.dumps(
                {"target": str(target), "action": "conflict", "error": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 3

    result: dict[str, object] = {
        "target": str(target),
        "apply": args.apply,
        "action": action,
        "source_commit": metadata["source_commit"],
        "source_dirty": metadata["source_dirty"],
        "source_sha256": metadata["content_sha256"],
        **details,
    }
    plan_basis: dict[str, object] = {
        "schema": 1,
        "operation": "sync-global-agents",
        "target": str(target),
        "action": action,
        "source_metadata": metadata,
        "current_sha256": sha256_bytes(current) if current is not None else None,
        "desired_sha256": sha256_bytes(desired),
        "adopt_local_tail_from": args.adopt_local_tail_from,
        "details": details,
    }
    plan_digest = digest_payload(plan_basis)
    result["plan_digest"] = plan_digest
    if not args.apply or action == "unchanged":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.approve_plan != plan_digest:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(
            "Application stopped: run dry-run, review it, and pass its exact plan_digest with --approve-plan.",
            file=sys.stderr,
        )
        return 3

    try:
        if current is not None:
            result["backup"] = str(backup(current, target))
        current_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
        atomic_write(target, desired, current_mode)
    except OSError as error:
        print(json.dumps({"error": f"global AGENTS sync failed: {error}"}, ensure_ascii=False), file=sys.stderr)
        return 4
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
