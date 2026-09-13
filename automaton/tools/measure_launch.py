#!/usr/bin/env python3
"""Launch OpenToonz under controlled settings and record baseline metrics."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def linux_memory_bytes(pid: int) -> tuple[int | None, int | None]:
    status_path = Path("/proc") / str(pid) / "status"
    try:
        fields = {}
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()

        def kibibytes(field: str) -> int | None:
            value = fields.get(field)
            if not value:
                return None
            return int(value.split()[0]) * 1024

        rss = kibibytes("VmRSS")
        peak = kibibytes("VmHWM")
        if rss is None:
            statm_path = status_path.with_name("statm")
            resident_pages = int(
                statm_path.read_text(encoding="utf-8").split()[1]
            )
            rss = resident_pages * os.sysconf("SC_PAGE_SIZE")
        return rss, peak if peak is not None else rss
    except (FileNotFoundError, PermissionError, ValueError):
        return None, None


def windows_memory_bytes(pid: int) -> tuple[int | None, int | None]:
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    process_query_information = 0x0400
    process_vm_read = 0x0010
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        process_query_information | process_vm_read, False, pid
    )
    if not handle:
        return None, None
    try:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            return None, None
        return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)
    finally:
        kernel32.CloseHandle(handle)


def process_memory_bytes(pid: int) -> tuple[int | None, int | None]:
    if sys.platform.startswith("linux"):
        return linux_memory_bytes(pid)
    if os.name == "nt":
        return windows_memory_bytes(pid)
    return None, None


def parse_environment(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"environment value must be NAME=VALUE: {value}")
        name, setting = value.split("=", 1)
        if not name:
            raise ValueError("environment variable name cannot be empty")
        parsed[name] = setting
    return parsed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--working-directory", type=Path)
    parser.add_argument("--stuff", type=Path)
    parser.add_argument("--profile", default="full", choices=("full",))
    parser.add_argument("--duration-seconds", type=float, default=15.0)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--terminate-grace", type=float, default=5.0)
    parser.add_argument("--software-rendering", action="store_true")
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("application_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    executable = arguments.executable.resolve()
    if not executable.is_file():
        print(f"executable not found: {executable}", file=sys.stderr)
        return 2
    if arguments.duration_seconds <= 0 or arguments.sample_interval <= 0:
        print("duration and sample interval must be positive", file=sys.stderr)
        return 2

    working_directory = (
        arguments.working_directory.resolve()
        if arguments.working_directory
        else executable.parent
    )
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = output.with_suffix(".stdout.log")
    stderr_path = output.with_suffix(".stderr.log")

    command = [str(executable)]
    if arguments.stuff:
        command.extend(["-TOONZROOT", str(arguments.stuff.resolve())])
    application_args = list(arguments.application_args)
    if application_args[:1] == ["--"]:
        application_args.pop(0)
    command.extend(application_args)

    environment = os.environ.copy()
    environment.update(
        {
            "QT_AUTO_SCREEN_SCALE_FACTOR": "0",
            "QT_SCALE_FACTOR": "1",
            "QT_ENABLE_HIGHDPI_SCALING": "0",
            "QT_LOGGING_RULES": "*.debug=false",
        }
    )
    if arguments.software_rendering:
        environment.update(
            {
                "LIBGL_ALWAYS_SOFTWARE": "1",
                "QT_OPENGL": "software",
                "QT_XCB_FORCE_SOFTWARE_OPENGL": "1",
            }
        )
    try:
        environment.update(parse_environment(arguments.env))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    start_utc = datetime.now(timezone.utc)
    start = time.monotonic()
    samples: list[dict] = []
    survived_interval = False
    launch_error: str | None = None
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

    with stdout_path.open("wb") as stdout_stream, stderr_path.open(
        "wb"
    ) as stderr_stream:
        try:
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                env=environment,
                stdout=stdout_stream,
                stderr=stderr_stream,
                creationflags=creation_flags,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            launch_error = str(exc)
            process = None

        if process is not None:
            deadline = start + arguments.duration_seconds
            while process.poll() is None and time.monotonic() < deadline:
                rss, peak = process_memory_bytes(process.pid)
                samples.append(
                    {
                        "elapsed_seconds": round(time.monotonic() - start, 3),
                        "rss_bytes": rss,
                        "reported_peak_rss_bytes": peak,
                    }
                )
                time.sleep(arguments.sample_interval)
            survived_interval = process.poll() is None
            if survived_interval:
                process.terminate()
                try:
                    process.wait(timeout=arguments.terminate_grace)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=arguments.terminate_grace)

    end = time.monotonic()
    valid_rss = [sample["rss_bytes"] for sample in samples if sample["rss_bytes"]]
    reported_peaks = [
        sample["reported_peak_rss_bytes"]
        for sample in samples
        if sample["reported_peak_rss_bytes"]
    ]
    result = {
        "schema_version": 1,
        "kind": "ot-automaton-phase1-baseline",
        "profile": arguments.profile,
        "started_utc": start_utc.isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "build_commit": os.environ.get("GITHUB_SHA"),
        "executable": str(executable),
        "executable_sha256": file_sha256(executable),
        "working_directory": str(working_directory),
        "command": command,
        "software_rendering": arguments.software_rendering,
        "observation_target_seconds": arguments.duration_seconds,
        "observed_seconds": round(end - start, 3),
        "survived_observation_interval": survived_interval,
        "process_exit_code": process.returncode if process is not None else None,
        "launch_error": launch_error,
        "sample_count": len(samples),
        "maximum_sampled_rss_bytes": max(valid_rss) if valid_rss else None,
        "maximum_reported_peak_rss_bytes": (
            max(reported_peaks) if reported_peaks else None
        ),
        "stdout_log": stdout_path.name,
        "stderr_log": stderr_path.name,
        "readiness_note": (
            "Phase 1 measures process survival, not semantic GUI readiness."
        ),
        "samples": samples,
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if survived_interval and launch_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
