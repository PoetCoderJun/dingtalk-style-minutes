#!/usr/bin/env python3
"""Release blockers must stay closed before the skill is published."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("DINGTALK_STYLE_MINUTES_SKILL", ROOT / "skill/dingtalk-style-minutes"))
FIXTURE_ROOT = ROOT / "tests/fixtures"
MODEL = FIXTURE_ROOT / "review-model.json"
TRANSCRIPT = FIXTURE_ROOT / "review-transcript.json"


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(arg) for arg in args], text=True, capture_output=True)


class ReleaseReadinessTest(unittest.TestCase):
    def test_missing_transcript_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = json.loads(MODEL.read_text(encoding="utf-8"))
            model["source"]["transcript_path"] = "missing-transcript.json"
            path = Path(directory) / "model.json"
            path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            result = run("python3", SKILL / "scripts/lint_content_model.py", path)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_document_renderer_requires_a_real_whiteboard_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "document.xml"
            result = run(
                "python3", SKILL / "scripts/render_feishu_document.py",
                "--model", MODEL,
                "--transcript", TRANSCRIPT,
                "--output", output,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_tone_is_rejected_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = copy.deepcopy(json.loads(MODEL.read_text(encoding="utf-8")))
            model["minutes"]["sections"][0]["tone"] = "not-a-tone"
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            result = run(
                "python3", SKILL / "scripts/lint_content_model.py",
                path, "--transcript", TRANSCRIPT,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_process_without_title_is_rejected_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = FIXTURE_ROOT / "meeting-model.json"
            transcript = FIXTURE_ROOT / "meeting-transcript.json"
            model = json.loads(model_path.read_text(encoding="utf-8"))
            process = next(section for section in model["minutes"]["sections"] if section["kind"] == "process")
            process["items"][0].pop("title")
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            result = run("python3", SKILL / "scripts/lint_content_model.py", path, "--transcript", transcript)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_svg_validator_rejects_off_canvas_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "board.svg"
            render = run(
                "python3", SKILL / "scripts/render_graphic_minutes.py",
                "--input", MODEL, "--output", svg,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            svg.write_text(
                svg.read_text(encoding="utf-8").replace('x="78" y="98"', 'x="99999" y="98"', 1),
                encoding="utf-8",
            )
            validate = run(
                "python3", SKILL / "scripts/validate_graphic_minutes.py",
                svg, "--model", MODEL,
            )
            self.assertNotEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_svg_validator_rejects_text_bbox_crossing_canvas_edge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "board.svg"
            render = run("python3", SKILL / "scripts/render_graphic_minutes.py", "--input", MODEL, "--output", svg)
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            svg.write_text(
                svg.read_text(encoding="utf-8").replace('x="78" y="98"', 'x="1679" y="98"', 1),
                encoding="utf-8",
            )
            validate = run("python3", SKILL / "scripts/validate_graphic_minutes.py", svg, "--model", MODEL)
            self.assertNotEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_transcriber_has_no_user_specific_default_path(self) -> None:
        source = (SKILL / "scripts/transcribe_media.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", source)
        self.assertNotIn("huzujun", source)


if __name__ == "__main__":
    unittest.main()
