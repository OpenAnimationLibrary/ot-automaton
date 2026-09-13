#!/usr/bin/env python3
"""Verify OT-Automaton provenance and its declared upstream delta."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


MARKER = "OT_AUTOMATON_ONLY"


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def is_infrastructure_path(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def verify(repository: Path, base_ref: str) -> tuple[dict, list[str]]:
    metadata = load_json(repository / "automaton" / "upstream-base.json")
    manifest = load_json(repository / "automaton" / "delta-manifest.json")

    expected_base = metadata["upstream_commit"]
    actual_base = run_git(repository, "rev-parse", base_ref)
    head = run_git(repository, "rev-parse", "HEAD")
    errors: list[str] = []

    if actual_base != expected_base:
        errors.append(
            f"{base_ref} resolves to {actual_base}, expected {expected_base}"
        )

    changed_output = run_git(
        repository,
        "diff",
        "--name-only",
        "--diff-filter=ACMRTUXB",
        f"{base_ref}...HEAD",
    )
    changed_paths = sorted(path for path in changed_output.splitlines() if path)
    prefixes = manifest["infrastructure_prefixes"]
    declared_source = set(manifest["source_paths"])
    actual_source = {
        path for path in changed_paths if not is_infrastructure_path(path, prefixes)
    }

    undeclared = sorted(actual_source - declared_source)
    stale = sorted(declared_source - actual_source)
    if undeclared:
        errors.append("undeclared source delta: " + ", ".join(undeclared))
    if stale:
        errors.append("stale source declaration: " + ", ".join(stale))

    for relative_path in sorted(actual_source & declared_source):
        source_path = repository / relative_path
        if not source_path.is_file():
            errors.append(f"declared source path is not a file: {relative_path}")
            continue
        try:
            content = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"cannot read {relative_path}: {exc}")
            continue
        if MARKER not in content:
            errors.append(f"missing {MARKER} marker: {relative_path}")

    report = {
        "schema_version": 1,
        "repository": str(repository),
        "base_ref": base_ref,
        "base_commit": actual_base,
        "head_commit": head,
        "changed_paths": changed_paths,
        "declared_source_paths": sorted(declared_source),
        "unexpected_paths": undeclared,
        "errors": errors,
        "status": "pass" if not errors else "fail",
    }
    return report, errors


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", default="upstream-master")
    parser.add_argument("--write-report", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    repository = arguments.repository.resolve()
    try:
        report, errors = verify(repository, arguments.base_ref)
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        print(f"OT-Automaton verification error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2) + "\n"
    print(rendered, end="")
    if arguments.write_report:
        output = arguments.write_report
        if not output.is_absolute():
            output = repository / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
