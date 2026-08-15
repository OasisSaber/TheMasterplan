#!/usr/bin/env python3
"""Contract tests for the v3.2.0 lightweight abstention boundary."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR_DIR))

from themasterplan import build_parser  # noqa: E402
from tmlib.inspect import detect_adapter  # noqa: E402

CORE = ROOT / "core/workflow.md"
OPENCODE_SKILL = ROOT / ".opencode/skills/themasterplan/SKILL.md"
OPENCODE_COMMAND = ROOT / ".opencode/commands/themasterplan.md"
GENERIC_ADAPTER = ROOT / "adapters/generic.md"
MANIFEST = ROOT / "distribution/manifest.json"
README = ROOT / "README.md"
ADOPTION = ROOT / "docs/adoption-guide.md"
ABSTENTION_DOC = ROOT / "docs/external-workflow-abstention.md"

REMOVED = (
    ROOT / "adapters/agent-orchestrator.md",
    ROOT / "adapters/trellis.md",
    ROOT / "examples/agent-orchestrator.yaml",
    ROOT / "docs/agent-orchestrator-integration.md",
    ROOT / "scripts/test_ao_adapter.py",
)


class AbstentionBoundaryTests(unittest.TestCase):
    def test_core_defines_ephemeral_abstention(self) -> None:
        body = CORE.read_text(encoding="utf-8")
        self.assertIn("ABSTAINED", body)
        self.assertIn("外部交付工作流", body)
        self.assertIn("不写入 `.themasterplan/state.json`", body)
        self.assertIn("不得按品牌", body)

    def test_direct_harness_is_not_itself_a_conflict(self) -> None:
        body = ABSTENTION_DOC.read_text(encoding="utf-8")
        self.assertIn("OpenCode", body)
        self.assertIn("不意味着外部治理接管", body)
        self.assertIn("谁拥有生命周期", body)

    def test_removed_orchestrator_assets_are_absent(self) -> None:
        self.assertEqual([p.as_posix() for p in REMOVED if p.exists()], [])

    def test_manifest_is_v320_and_generic_only(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["distribution_version"], "v4.0.0")
        self.assertEqual(manifest["components"]["adapters"], ["generic"])
        destinations = {entry["destination"] for entry in manifest["files"]}
        self.assertIn("adapters/generic.md", destinations)
        self.assertNotIn("adapters/trellis.md", destinations)
        self.assertNotIn("adapters/agent-orchestrator.md", destinations)

    def test_plan_adopt_parser_accepts_only_generic_adapter(self) -> None:
        parser = build_parser()
        common = [
            "plan-adopt", "--source", ".", "--profile", "git",
            "--validation-path", "scripts/check.sh", "--output", "plan.json",
        ]
        args = parser.parse_args(common + ["--adapter", "generic"])
        self.assertEqual(args.adapter, "generic")
        for retired in ("trellis", "agent-orchestrator"):
            with self.assertRaises(SystemExit):
                parser.parse_args(common + ["--adapter", retired])

    def test_inspect_does_not_select_external_workflow_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".trellis").mkdir()
            self.assertEqual(detect_adapter(project), "generic")

    def test_opencode_entry_abstains_for_external_owner(self) -> None:
        for path in (OPENCODE_SKILL, OPENCODE_COMMAND):
            body = path.read_text(encoding="utf-8")
            self.assertIn("ABSTAINED", body)
            self.assertIn("external", body.lower())
            self.assertNotIn("adapters/agent-orchestrator.md", body)

    def test_opencode_entry_carries_pr_body_contract(self) -> None:
        body = OPENCODE_SKILL.read_text(encoding="utf-8")
        for marker in (
            "## Result", "## Changes", "## Verification",
            "## Agent self-review", "满足 Issue 或明确人类授权",
            "没有扩大任务范围", "已阅读完整 diff", "必要验证已通过",
            "没有遗留调试代码、临时文件或缓存",
        ):
            self.assertIn(marker, body)

    def test_generic_adapter_is_thin_boundary(self) -> None:
        body = GENERIC_ADAPTER.read_text(encoding="utf-8")
        self.assertIn("薄 Harness", body)
        self.assertIn("ABSTAINED", body)
        self.assertIn("不维护外部工作流兼容层", body)

    def test_public_docs_no_longer_claim_orchestrator_support(self) -> None:
        readme = README.read_text(encoding="utf-8")
        adoption = ADOPTION.read_text(encoding="utf-8")
        self.assertNotIn("Agent Orchestrator 支持矩阵", readme)
        self.assertNotIn("Agent Orchestrator 采用", adoption)
        self.assertIn("ABSTAINED", readme)
        self.assertIn("外部交付工作流", adoption)


if __name__ == "__main__":
    unittest.main()
