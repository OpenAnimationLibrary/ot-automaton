#!/usr/bin/env python3
"""Validate and package the animated-shapes OpenToonz acceptance project."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a valid PNG header: {path}")
    return struct.unpack(">II", data[16:24])


def validate(root: Path) -> dict[str, object]:
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    scene = root / str(manifest["scene"])
    if not scene.is_file() or scene.stat().st_size == 0:
        failures.append("OpenToonz scene file is missing or empty")
        scene_text = ""
    else:
        scene_text = scene.read_text(encoding="utf-8", errors="replace")

    expected_aliases = [f"+drawings/{name}" for name in ("circle", "square", "triangle")]
    for alias in expected_aliases:
        if alias not in scene_text:
            failures.append(f"scene does not contain portable project alias {alias!r}")

    script_log = root / "evidence" / "create-scene.log"
    log_text = script_log.read_text(encoding="utf-8", errors="replace") if script_log.exists() else ""
    marker = re.search(r"OT_AUTOMATON_SCENE_CREATED frames=(\d+) columns=(\d+)", log_text)
    if not marker:
        failures.append("OpenToonz automation success marker is missing")
        observed_frames = observed_columns = None
    else:
        observed_frames, observed_columns = int(marker.group(1)), int(marker.group(2))
        if observed_frames != int(manifest["frame_count"]):
            failures.append(f"scene has {observed_frames} frames, expected {manifest['frame_count']}")
        if observed_columns != 3:
            failures.append(f"scene has {observed_columns} columns, expected 3")

    drawing_files = sorted((root / "drawings").glob("*.png"))
    expected_drawings = int(manifest["frame_count"]) * 3
    if len(drawing_files) != expected_drawings:
        failures.append(f"found {len(drawing_files)} source frames, expected {expected_drawings}")

    renders = sorted((root / "outputs").glob("render.*.png"))
    if len(renders) != 3:
        failures.append(f"found {len(renders)} representative renders, expected 3")
    for path in drawing_files + renders:
        try:
            png_dimensions(path)
        except ValueError as error:
            failures.append(str(error))

    screenshot = root / "evidence" / "opentoonz-scene.png"
    if not screenshot.exists():
        failures.append("OpenToonz scene screenshot is missing")
    else:
        try:
            png_dimensions(screenshot)
        except ValueError as error:
            failures.append(str(error))

    reopen_log = root / "evidence" / "reopen.log"
    if not reopen_log.exists():
        failures.append("scene reopen log is missing")

    report: dict[str, object] = {
        "schema_version": 1,
        "test": "animated-shapes",
        "passed": not failures,
        "failures": failures,
        "observed": {
            "frames": observed_frames,
            "columns": observed_columns,
            "source_asset_count": len(drawing_files),
            "render_count": len(renders),
            "scene_size_bytes": scene.stat().st_size if scene.exists() else 0,
        },
    }
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=True)
    report_path = evidence / "verification.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def package(root: Path, destination: Path) -> None:
    root = root.resolve()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.resolve() != destination:
                archive.write(path, Path(root.name) / path.relative_to(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.project_root)
    package(args.project_root, args.zip_path)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
