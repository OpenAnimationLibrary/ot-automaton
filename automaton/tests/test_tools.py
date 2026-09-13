from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import measure_launch  # noqa: E402
import verify_repository  # noqa: E402


class VerifyRepositoryTests(unittest.TestCase):
    def test_exact_infrastructure_file_is_allowed(self) -> None:
        self.assertTrue(
            verify_repository.is_infrastructure_path(
                "AUTOMATON_SCOPE.md", ["AUTOMATON_SCOPE.md"]
            )
        )

    def test_infrastructure_prefix_is_allowed(self) -> None:
        self.assertTrue(
            verify_repository.is_infrastructure_path(
                "automaton/tools/check.py", ["automaton/"]
            )
        )

    def test_similar_prefix_is_rejected(self) -> None:
        self.assertFalse(
            verify_repository.is_infrastructure_path(
                "automaton-unrelated/file.cpp", ["automaton/"]
            )
        )


class MeasureLaunchTests(unittest.TestCase):
    def test_environment_parser(self) -> None:
        self.assertEqual(
            measure_launch.parse_environment(["A=one", "B=two=three"]),
            {"A": "one", "B": "two=three"},
        )

    def test_environment_parser_rejects_missing_separator(self) -> None:
        with self.assertRaises(ValueError):
            measure_launch.parse_environment(["INVALID"])

    def test_current_process_memory_probe_does_not_raise(self) -> None:
        rss, peak = measure_launch.process_memory_bytes(os.getpid())
        if sys.platform.startswith("linux") or os.name == "nt":
            self.assertTrue(rss is None or isinstance(rss, int))
            self.assertTrue(peak is None or isinstance(peak, int))

    def test_software_renderer_is_selected_for_current_platform(self) -> None:
        environment = measure_launch.software_rendering_environment()
        if os.name == "nt":
            self.assertEqual(environment["QT_OPENGL"], "angle")
            self.assertEqual(environment["QT_ANGLE_PLATFORM"], "warp")
        else:
            self.assertEqual(environment["QT_OPENGL"], "software")
            self.assertEqual(environment["LIBGL_ALWAYS_SOFTWARE"], "1")


if __name__ == "__main__":
    unittest.main()
