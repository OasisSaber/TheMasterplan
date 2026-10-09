"""Version identity and truthful pre-publication contracts for v5.1.0."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
VERSION = "v5.1.0"

class ReleasePreparationTests(unittest.TestCase):
    def test_manifest_target_version(self):
        manifest = json.loads((ROOT / "distribution/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["distribution_version"], VERSION)
        self.assertEqual(manifest["schema_version"], 1)

    def test_consumer_template_pair_and_publication_guard(self):
        text = (ROOT / "distribution/templates/consumer-workflow.yml").read_text(encoding="utf-8")
        self.assertIn("themasterplan-check.yml@" + VERSION, text)
        self.assertIn("policy-ref: " + VERSION, text)
        self.assertIn("Tag", text)
        self.assertIn("发布", text)

    def test_current_examples_and_release_status_are_explicit(self):
        for relative in ("README.md", "docs/actions-interface.md", "docs/adoption-guide.md", "docs/release-channels.md"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("themasterplan-check.yml@" + VERSION, text)
                self.assertIn("policy-ref: " + VERSION, text)
                self.assertIn("发布状态", text)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("themasterplan-check.yml@" + VERSION, agents)
        self.assertIn("发布状态", agents)

    def test_release_notes_document_upgrade_limits_and_sources(self):
        notes = (ROOT / "docs/releases/v5.1.0.md").read_text(encoding="utf-8")
        for required in (VERSION, "发布状态", "旧计划", "旧执行器", "v1", "v5.0.0", "崩溃原子", "人类审阅"):
            self.assertIn(required, notes)
        for number in (94, 96, 98, 100):
            self.assertIn("https://github.com/OasisSaber/TheMasterplan/pull/" + str(number), notes)

    def test_frozen_compatibility_and_published_baseline_remain_documented(self):
        channels = (ROOT / "docs/release-channels.md").read_text(encoding="utf-8")
        self.assertIn("v5.0.0      历史不可变 Release tag", channels)
        self.assertIn("v1", channels)
        self.assertIn("冻结", channels)
        self.assertIn("aw-check.yml@v1", channels)

if __name__ == "__main__":
    unittest.main()
