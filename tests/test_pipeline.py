#!/usr/bin/env python3
"""Portable positive and negative tests for the public skill package."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("DINGTALK_STYLE_MINUTES_SKILL", ROOT / "skill/dingtalk-style-minutes"))
FIXTURES = ROOT / "tests/fixtures"


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(arg) for arg in args], text=True, capture_output=True)


class PipelineTest(unittest.TestCase):
    def test_review_and_meeting_use_distinct_information_architectures(self) -> None:
        review = json.loads((FIXTURES / "review-model.json").read_text(encoding="utf-8"))
        meeting = json.loads((FIXTURES / "meeting-model.json").read_text(encoding="utf-8"))
        review_kinds = [section["kind"] for section in review["minutes"]["sections"]]
        meeting_kinds = [section["kind"] for section in meeting["minutes"]["sections"]]
        self.assertNotEqual(review_kinds, meeting_kinds)
        self.assertIn("comparison", review_kinds)
        self.assertIn("process", meeting_kinds)

    def test_fixture_pipeline_and_corruption_rejection(self) -> None:
        for stem in ("review", "meeting"):
            with self.subTest(stem=stem), tempfile.TemporaryDirectory() as directory:
                model = FIXTURES / f"{stem}-model.json"
                transcript = FIXTURES / f"{stem}-transcript.json"
                temp = Path(directory)
                svg = temp / "board.svg"
                doc = temp / "document.xml"
                commands = [
                    ("lint", "python3", SKILL / "scripts/lint_content_model.py", model, "--transcript", transcript),
                    ("render SVG", "python3", SKILL / "scripts/render_graphic_minutes.py", "--input", model, "--output", svg),
                    ("validate SVG", "python3", SKILL / "scripts/validate_graphic_minutes.py", svg, "--model", model),
                    ("render document", "python3", SKILL / "scripts/render_feishu_document.py", "--model", model, "--transcript", transcript, "--output", doc, "--whiteboard-token", "wbcn-test-fixture"),
                    ("validate document", "python3", SKILL / "scripts/validate_feishu_document.py", doc, "--model", model, "--transcript", transcript, "--whiteboard-token", "wbcn-test-fixture"),
                ]
                for label, *command in commands:
                    result = run(*command)
                    self.assertEqual(result.returncode, 0, f"{label}: {result.stdout}{result.stderr}")
                original = doc.read_text(encoding="utf-8")
                doc.write_text(original.replace("<h2>概述</h2>", "<h2>概述</h2><h2>章节导航</h2>", 1), encoding="utf-8")
                corrupt = run("python3", SKILL / "scripts/validate_feishu_document.py", doc, "--model", model, "--transcript", transcript, "--whiteboard-token", "wbcn-test-fixture")
                self.assertNotEqual(corrupt.returncode, 0)

    def test_content_driven_height_for_every_card_like_kind(self) -> None:
        spec = importlib.util.spec_from_file_location("renderer", SKILL / "scripts/render_graphic_minutes.py")
        renderer = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(renderer)
        def card(identifier: str, dense: bool = False) -> dict:
            bullets = ["短结论"] if not dense else ["这是一条包含机制、限制和执行细节的长说明，用来确认内容增加后容器会随之长高。" for _ in range(4)]
            return {"id": identifier, "title": "短标题", "bullets": bullets, "takeaway": "结论", "source_segment_ids": ["seg-1"]}
        cases = [
            ({"kind":"cards","items":[card("a")]},{"kind":"cards","items":[card("a",True)]}),
            ({"kind":"process","items":[card("a")]},{"kind":"process","items":[card("a",True)]}),
            ({"kind":"comparison","items":[card("a"),card("b")]},{"kind":"comparison","items":[card("a",True),card("b",True)]}),
            ({"kind":"metrics","items":[{"label":"准确率","value":"90%","note":"短注释"}]},{"kind":"metrics","items":[{"label":"准确率变化","value":"约 50% 到 90%","note":"包含口径和边界条件的较长注释，用来验证高度随文本增长。"}]}),
            ({"kind":"quotes","items":[{"quote":"短引语"}]},{"kind":"quotes","items":[{"quote":"一段需要换行展示的长引语。"*20}]}),
            ({"kind":"synthesis","text":"短结论"},{"kind":"synthesis","text":"包含原因、机制与影响的综合判断。"*20}),
        ]
        for sparse, dense in cases:
            with self.subTest(kind=sparse["kind"]):
                self.assertGreater(renderer.section_height(dense), renderer.section_height(sparse))


if __name__ == "__main__":
    unittest.main()
