"""Validate the Dokushodo documentation contract without exposing file contents."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = 1
CANONICAL_ROOT = (
    "ARCHITECTURE.md",
    "CONFIGURATION.md",
    "DEPLOYMENT.md",
    "DESIGN.md",
    "EVIDENCE.md",
    "OPERATIONS.md",
    "STATUS.md",
    "STORAGE.md",
    "TRANSLATION.md",
)
TRANSITIONAL_ROOT = {"HISTORY.md", "WORK.md"}
ALLOWED_DOC_DIRECTORIES = {"archive", "design", "plans"}
REQUIRED_FRONT_MATTER = {
    "title": str,
    "document_role": str,
    "authority": str,
    "scope": str,
    "audience": list,
    "update_triggers": list,
    "owned_concerns": list,
}
DOCUMENT_ROLES = {"normative", "reference", "procedural", "status", "evidence"}
WORK_STATES = {"planned", "active", "blocked", "deferred", "complete", "superseded"}
EVIDENCE_DISPOSITIONS = {"passed", "failed", "blocked", "partial", "unavailable", "not_run"}
PLAN_A = "docs/plans/DOKUSHODO_AGENTS_AND_CANONICAL_DOCUMENTATION_STANDARDIZATION_PLAN.md"
PLAN_B = "docs/plans/DOKUSHODO_COMPLETE_PUBLIC_HOSTED_EXECUTION_PLAN.md"
OLD_PATH_MARKERS = ("docs/WORK.md", "docs/HISTORY.md", "docs/DOCUMENTATION_PLAN.md")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:ghp|github_pat|sk|xox[baprs])-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|redis)://[^\s/]+:[^\s/@]+@[^\s]+"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?key|secret[_-]?key|token)\s*[:=]\s*[A-Za-z0-9+/=_-]{24,}"),
)
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\n]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FRONT_KEY_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$")
STATUS_FIELD_PATTERN = re.compile(
    r"^\s*(?:work_state|evidence_disposition|disposition|status):\s*`?([a-z_]+)`?\s*$",
    re.IGNORECASE,
)


class Audit:
    """Collect only stable categories and counts, never matching content."""

    def __init__(self, root: Path, mode: str) -> None:
        self.root = root
        self.mode = mode
        self.counts: Counter[str] = Counter()
        self.checked_paths: set[str] = set()

    def check(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            relative = path.as_posix()
        self.checked_paths.add(relative)

    def violation(self, category: str, amount: int = 1) -> None:
        self.counts[category] += amount

    def result(self) -> dict[str, Any]:
        candidate_sha = "unavailable"
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", completed.stdout.strip()):
                candidate_sha = completed.stdout.strip()
        except OSError, subprocess.SubprocessError:
            pass
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": self.mode,
            "candidate_sha": candidate_sha,
            "checked_paths": sorted(self.checked_paths),
            "violation_categories": [
                {"category": category, "count": self.counts[category]} for category in sorted(self.counts)
            ],
            "violation_count": sum(self.counts.values()),
            "exit_code": 1 if self.counts else 0,
        }


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_yaml_string(item.strip()) for item in inner.split(",")]
    return _strip_yaml_string(value)


def _strip_yaml_string(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_front_matter(text: str) -> tuple[dict[str, Any] | None, str, bool]:
    """Parse the intentionally small YAML subset used by canonical docs."""

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text, False
    closing_index = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if closing_index is None:
        return None, text, True
    fields: dict[str, Any] = {}
    current_list: str | None = None
    for line in lines[1:closing_index]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace() and stripped.startswith("-") and current_list is not None:
            if not isinstance(fields.get(current_list), list):
                fields[current_list] = []
            fields[current_list].append(_strip_yaml_string(stripped[1:].strip()))
            continue
        match = FRONT_KEY_PATTERN.match(stripped)
        if not match:
            fields["__malformed__"] = True
            current_list = None
            continue
        key, raw_value = match.groups()
        value = _parse_scalar(raw_value or "")
        fields[key] = value
        current_list = key if isinstance(value, list) and not raw_value else None
    body = "".join(lines[closing_index + 1 :])
    return fields, body, True


def _iter_markdown_lines(text: str) -> tuple[list[str], bool]:
    visible: list[str] = []
    fence: str | None = None
    malformed = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if fence is None:
                fence = "`"
            elif fence == "`":
                fence = None
            continue
        if stripped.startswith("~~~"):
            if fence is None:
                fence = "~"
            elif fence == "~":
                fence = None
            continue
        if fence is None:
            visible.append(line)
    if fence is not None:
        malformed = True
    return visible, malformed


def _case_correct(path: Path) -> bool:
    current = (path.anchor and Path(path.anchor)) or Path(path.root)
    for part in path.parts:
        if part in (path.anchor, path.root, ""):
            continue
        if not current.exists() or not current.is_dir():
            return False
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def _validate_local_links(audit: Audit, path: Path, visible_lines: Iterable[str]) -> None:
    source_dir = path.parent
    for line in visible_lines:
        for match in LINK_PATTERN.finditer(line):
            target = match.group(1).strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split()[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or target.startswith("#"):
                continue
            local_target = unquote(parsed.path)
            resolved = (source_dir / local_target).resolve()
            try:
                resolved.relative_to(audit.root.resolve())
            except ValueError:
                audit.violation("link_outside_repository")
                continue
            if not resolved.exists():
                audit.violation("broken_link")
            elif not _case_correct(resolved):
                audit.violation("case_incorrect_link")


def _validate_front_matter(audit: Audit, path: Path, text: str, body: str, front: dict[str, Any] | None) -> None:
    if front is None:
        audit.violation("front_matter")
        return
    if front.get("__malformed__"):
        audit.violation("malformed_front_matter")
    for key, expected_type in REQUIRED_FRONT_MATTER.items():
        value = front.get(key)
        if not isinstance(value, expected_type) or (isinstance(value, (str, list)) and not value):
            audit.violation("front_matter_field")
    if isinstance(front.get("document_role"), str) and front["document_role"] not in DOCUMENT_ROLES:
        audit.violation("document_role")
    visible, malformed = _iter_markdown_lines(body)
    if malformed:
        audit.violation("malformed_fence")
    headings: list[tuple[int, str]] = []
    for line in visible:
        heading = HEADING_PATTERN.match(line)
        if heading:
            headings.append((len(heading.group(1)), heading.group(2)))
    if not headings or not headings[0][1]:
        audit.violation("missing_h1")
    else:
        first_content = next((line for line in body.splitlines() if line.strip()), "")
        if not HEADING_PATTERN.match(first_content) or not first_content.startswith("# "):
            audit.violation("h1_not_immediate")
    if sum(1 for level, _ in headings if level == 1) != 1:
        audit.violation("h1_count")
    previous_level = 0
    for level, _ in headings:
        if previous_level and level > previous_level + 1:
            audit.violation("heading_skip")
        previous_level = level
    top_level_names = [name.lower() for level, name in headings if level == 2]
    if len(top_level_names) != len(set(top_level_names)):
        audit.violation("duplicate_heading")
    anchors = re.findall(r"\{#([A-Za-z0-9_.:-]+)\}", body)
    if len(anchors) != len(set(anchors)):
        audit.violation("duplicate_anchor")
    for line in visible:
        status_match = STATUS_FIELD_PATTERN.match(line)
        if not status_match:
            continue
        value = status_match.group(1).lower()
        if value not in WORK_STATES and value not in EVIDENCE_DISPOSITIONS:
            audit.violation("invalid_status")
    _validate_local_links(audit, path, visible)


def _validate_plan_metadata(audit: Audit, path: Path, text: str) -> None:
    front, _, has_front = parse_front_matter(text)
    if not has_front or front is None:
        audit.violation("plan_front_matter")
        return
    if front.get("canonical_truth") is not False and str(front.get("canonical_truth", "")).lower() != "false":
        audit.violation("plan_canonical_truth")
    if path.as_posix() == PLAN_A:
        if front.get("successor") != "dokushodo-public-hosted-evidence":
            audit.violation("plan_interface")
        if front.get("successor_path") != PLAN_B:
            audit.violation("plan_interface")
    if path.as_posix() == PLAN_B:
        if front.get("predecessor") != "dokushodo-docs-standardization":
            audit.violation("plan_interface")
        if front.get("predecessor_path") != PLAN_A:
            audit.violation("plan_interface")
        if front.get("predecessor_handoff") != "artifacts/documentation-standardization/handoff.json":
            audit.violation("plan_interface")


def _is_exempt_legacy_path(path: Path, root: Path) -> bool:
    """Allow only bounded migration or historical marker locations."""
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.as_posix()
    return (
        relative in {PLAN_A, PLAN_B, "tools/docs_check.py"}
        or relative.startswith("docs/archive/")
        or relative.startswith("artifacts/")
    )


def _iter_text_files(root: Path, allowed_suffixes: set[str] | None = None) -> Iterable[Path]:
    ignored = {
        ".git",
        ".venv",
        "node_modules",
        "graphify-out",
        ".codegraph",
        "artifacts",
        ".next",
        ".next-dev",
        "out",
        "build",
        "dist",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".pyright",
        ".cache",
        ".local",
    }
    suffixes = allowed_suffixes or {".md", ".mdx", ".py", ".ps1", ".psm1", ".yml", ".yaml", ".json", ".toml", ".txt"}
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except OSError, subprocess.SubprocessError:
        tracked = None
    if tracked is not None and tracked.returncode == 0:
        for raw_path in tracked.stdout.split(b"\0"):
            if not raw_path:
                continue
            path = root / os.fsdecode(raw_path)
            if path.is_file() and path.suffix.lower() in suffixes:
                yield path
        return
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if name not in ignored)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.suffix.lower() in suffixes:
                yield path


def _scan_sensitive_patterns(audit: Audit, root: Path) -> None:
    documentation_suffixes = {".md", ".mdx", ".yml", ".yaml", ".json", ".toml"}
    for path in _iter_text_files(root, documentation_suffixes):
        relative = path.relative_to(root).as_posix()
        if not (relative.startswith("docs/") or relative == "AGENTS.md" or relative.startswith(".github/")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeError:
            audit.violation("unreadable_text")
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match and pattern.pattern.lower().startswith("(?i)\\b(?:postgres"):
                candidate = match.group(0).lower()
                if any(marker in candidate for marker in ("localhost", "127.0.0.1", "<password>", "example")):
                    match = None
            if match:
                audit.violation("secret_pattern")


def _scan_stale_references(audit: Audit, root: Path) -> None:
    for path in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeError:
            continue
        if _is_exempt_legacy_path(path, root):
            continue
        for marker in OLD_PATH_MARKERS:
            if marker in text:
                audit.violation("stale_active_path")
                break


def check_repository(root: Path, migration_mode: bool = False) -> Audit:
    mode = "migration" if migration_mode else "strict"
    audit = Audit(root, mode)
    docs_root = root / "docs"
    if not docs_root.is_dir():
        audit.violation("missing_docs_root")
        return audit
    root_docs = {path.name for path in docs_root.glob("*.md")}
    if migration_mode:
        required_current = set(CANONICAL_ROOT[:4]) | {"OPERATIONS.md", "STORAGE.md", "TRANSLATION.md"}
        if not required_current.issubset(root_docs):
            audit.violation("migration_root_document")
    elif root_docs != set(CANONICAL_ROOT):
        audit.violation("extra_root_document", len(root_docs.symmetric_difference(set(CANONICAL_ROOT))))
    for directory in docs_root.rglob("*"):
        if directory.is_dir():
            relative = directory.relative_to(docs_root).parts
            if relative and relative[0] not in ALLOWED_DOC_DIRECTORIES:
                audit.violation("unapproved_docs_directory")
    owners: dict[str, str] = {}
    for name in CANONICAL_ROOT:
        path = docs_root / name
        if not path.exists():
            if not migration_mode:
                audit.violation("missing_canonical_document")
            continue
        audit.check(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeError:
            audit.violation("unreadable_text")
            continue
        front, body, _ = parse_front_matter(text)
        if migration_mode and name in TRANSITIONAL_ROOT:
            continue
        if not migration_mode:
            _validate_front_matter(audit, path, text, body, front)
        if isinstance(front, dict):
            concerns = front.get("owned_concerns", [])
            if isinstance(concerns, list):
                for concern in concerns:
                    if not isinstance(concern, str):
                        audit.violation("front_matter_field")
                    elif concern in owners:
                        audit.violation("duplicate_owned_concern")
                    else:
                        owners[concern] = name
    plans_root = docs_root / "plans"
    if plans_root.is_dir():
        for plan_path in plans_root.glob("*.md"):
            audit.check(plan_path)
            try:
                _validate_plan_metadata(audit, plan_path, plan_path.read_text(encoding="utf-8"))
            except OSError, UnicodeError:
                audit.violation("unreadable_text")
    if not migration_mode:
        _scan_stale_references(audit, root)
    _scan_sensitive_patterns(audit, root)
    return audit


def _fixture_front(title: str, role: str = "normative", concern: str = "fixture") -> str:
    return "\n".join(
        [
            "---",
            f"title: {title}",
            f"document_role: {role}",
            "authority: canonical",
            "scope: fixture",
            "audience:",
            "  - agents",
            "update_triggers:",
            "  - fixture change",
            "owned_concerns:",
            f"  - {concern}",
            "---",
            f"# {title}",
            "",
            "Purpose and authority boundary.",
            "",
        ]
    )


def _self_test_case(name: str, root: Path, expected: str) -> tuple[str, bool]:
    audit = check_repository(root)
    return name, audit.counts.get(expected, 0) > 0


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="dokushodo-docs-check-") as temporary:
        root = Path(temporary)
        docs = root / "docs"
        docs.mkdir()
        for index, name in enumerate(CANONICAL_ROOT):
            role = "status" if name == "STATUS.md" else "evidence" if name == "EVIDENCE.md" else "normative"
            (docs / name).write_text(
                _fixture_front(name.removesuffix(".md"), role, f"concern-{index}"), encoding="utf-8"
            )
        baseline = check_repository(root)
        cases: list[tuple[str, str, str | None]] = [("pass", "", None)]
        cases.extend(
            [
                ("broken_link", "\n[missing](missing.md)\n", "broken_link"),
                ("duplicate_heading", "\n## Duplicate\n\n## Duplicate\n", "duplicate_heading"),
                ("stale_active_path", "\ndocs/WORK.md\n", "stale_active_path"),
                ("invalid_status", "\nstatus: questionable\n", "invalid_status"),
                ("secret_pattern", "\n-----BEGIN PRIVATE KEY-----\n", "secret_pattern"),
            ]
        )
        outcomes: dict[str, bool] = {"pass": not baseline.counts}
        source = docs / "ARCHITECTURE.md"
        original = source.read_text(encoding="utf-8")
        for name, suffix, expected in cases[1:]:
            source.write_text(original + suffix, encoding="utf-8")
            _, passed = _self_test_case(name, root, expected or name)
            outcomes[name] = passed
            source.write_text(original, encoding="utf-8")
        extra = docs / "EXTRA.md"
        extra.write_text(_fixture_front("Extra"), encoding="utf-8")
        outcomes["extra_root_document"] = check_repository(root).counts.get("extra_root_document", 0) > 0
        extra.unlink()
        source.write_text(original.removeprefix("---\n"), encoding="utf-8")
        outcomes["malformed_front_matter"] = check_repository(root).counts.get("front_matter", 0) > 0
        failed = sorted(name for name, passed in outcomes.items() if not passed)
        result = {
            "schema_version": SCHEMA_VERSION,
            "mode": "self_test",
            "case_count": len(outcomes),
            "passed_cases": len(outcomes) - len(failed),
            "failed_cases": len(failed),
            "failed_case_names": failed,
            "exit_code": 1 if failed else 0,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return result["exit_code"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--migration-mode", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()
    root = args.root.resolve()
    audit = check_repository(root, migration_mode=args.migration_mode)
    print(json.dumps(audit.result(), indent=2, sort_keys=True))
    return audit.result()["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
