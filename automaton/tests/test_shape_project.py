from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import create_shape_project  # noqa: E402


class CreateShapeProjectTests(unittest.TestCase):
    def test_creates_three_deterministic_animated_levels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "animated-shapes-project"
            manifest = create_shape_project.create_project(root)

            self.assertEqual(manifest["frame_count"], 12)
            self.assertEqual(len(manifest["levels"]), 3)
            self.assertEqual(len(list((root / "drawings").glob("*.png"))), 36)
            self.assertEqual(
                (root / "drawings" / "circle.0001.png").read_bytes()[:8],
                b"\x89PNG\r\n\x1a\n",
            )
            self.assertNotEqual(
                (root / "drawings" / "circle.0001.png").read_bytes(),
                (root / "drawings" / "circle.0012.png").read_bytes(),
            )

    def test_script_and_manifest_describe_portable_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "animated-shapes-project"
            create_shape_project.create_project(root)
            script = (root / "scripts" / "create_scene.toonzscript").read_text()
            manifest = json.loads((root / "manifest.json").read_text())

            self.assertIn("new Scene()", script)
            self.assertIn("scene.save", script)
            self.assertIn("OT_AUTOMATON_SCENE_CREATED", script)
            self.assertEqual(manifest["scene"], "scenes/animated-shapes.tnz")
            self.assertTrue((root / "animated-shapes_otprj.xml").exists())


if __name__ == "__main__":
    unittest.main()
