#!/usr/bin/env python3
"""Public package metadata and links must remain portable and consistent."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill/dingtalk-style-minutes"


class MetadataTest(unittest.TestCase):
    def test_skill_and_interface_names_match(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        interface = yaml.safe_load((SKILL / "agents/openai.yaml").read_text(encoding="utf-8"))["interface"]
        self.assertEqual(frontmatter["name"], "dingtalk-style-minutes")
        self.assertEqual(interface["display_name"], "DingTalk-style Minutes")
        self.assertIn("Chinese", frontmatter["description"])
        self.assertNotIn("/Users/", text)

    def test_skill_documents_cloud_or_local_asr_choice(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("DASHSCOPE_API_KEY", text)
        self.assertIn("FunASR", text)
        self.assertIn("transcript.json", text)

    def test_all_relative_markdown_links_exist(self) -> None:
        for document in (ROOT / "README.md", ROOT / "README_EN.md", SKILL / "SKILL.md"):
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                self.assertTrue((document.parent / target).resolve().exists(), f"{document}: {target}")

    def test_no_compiled_or_sensitive_case_artifacts(self) -> None:
        files = [path for path in ROOT.rglob("*") if path.is_file()]
        packaged = [path for path in files if "tests" not in path.parts]
        self.assertFalse([path for path in packaged if path.suffix in {".pyc", ".pyo"}])
        public_files = [
            path for path in files
            if "tests" not in path.parts and path.suffix in {".md", ".py", ".json", ".yaml", ".yml"}
        ]
        searchable = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in public_files)
        self.assertNotIn("Bridgewater", searchable)
        self.assertNotIn("Pocket Analyst", searchable)
        self.assertNotIn("/Users/", searchable)


if __name__ == "__main__":
    unittest.main()
