#!/usr/bin/env python3
"""Contract tests for the v5 Context-Minimal Reform."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR))

from themasterplan import build_parser  # noqa: E402
from tmlib.inspect import inspect  # noqa: E402

AGENTS = ROOT / "AGENTS.md"
WORKFLOW = ROOT / "core/workflow.md"
SKILL = ROOT / "skills/themasterplan/SKILL.md"
OPENCODE_SKILL = ROOT / ".opencode/skills/themasterplan/SKILL.md"
OPENCODE_COMMAND = ROOT / ".opencode/commands/themasterplan.md"
MANIFEST = ROOT / "distribution/manifest.json"
SCHEMA = ROOT / "distribution/schema.json"
STATE_DOC = ROOT / "docs/themasterplan-state-format.md"
README = ROOT / "README.md"
ADOPTION = ROOT / "docs/adoption-guide.md"

DELETED = (
    ROOT / "adapters/generic.md",
    ROOT / "skills/themasterplan/references/smoke-test.md",
)


class ContextMinimalContractTests(unittest.TestCase):
    def test_manifest_is_v5_without_adapters(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["distribution_version"], "v5.0.0")
        self.assertNotIn("adapters", manifest.get("components", {}))
        destinations = {entry["destination"] for entry in manifest["files"]}
        self.assertFalse(any(path.startswith("adapters/") for path in destinations))

    def test_schema_has_no_adapter_component(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        props = schema["properties"]["components"]["properties"]
        self.assertNotIn("adapters", props)

    def test_deleted_context_duplicates_are_absent(self) -> None:
        self.assertEqual([str(path) for path in DELETED if path.exists()], [])

    def test_plan_adopt_has_no_adapter_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "plan-adopt", "--source", ".", "--profile", "git",
            "--validation-path", "scripts/check.sh", "--output", "plan.json",
        ])
        self.assertFalse(hasattr(args, "adapter"))
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "plan-adopt", "--source", ".", "--profile", "git",
                "--adapter", "generic",
                "--validation-path", "scripts/check.sh", "--output", "plan.json",
            ])

    def test_inspect_has_no_adapter_surface(self) -> None:
        result = inspect(ROOT)
        self.assertNotIn("detected_adapter", result)

    def test_agents_is_context_router_not_preload_itinerary(self) -> None:
        body = AGENTS.read_text(encoding="utf-8")
        self.assertIn("## Context Router", body)
        self.assertIn("## Completion Contract", body)
        self.assertIn("不要因为文件存在就读取它", body)
        self.assertNotIn("## 加载顺序", body)
        self.assertNotIn("adapters/generic.md", body)

    def test_skill_is_minimal_router(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        nonempty = [line for line in body.splitlines() if line.strip()]
        self.assertLessEqual(len(nonempty), 35)
        self.assertIn("Context Router", body)
        self.assertNotIn("check-update", body)
        self.assertNotIn("## Result", body)
        self.assertNotIn("Agent self-review", body)
        self.assertNotIn("adapters/generic.md", body)

    def test_opencode_surfaces_are_thin(self) -> None:
        skill = OPENCODE_SKILL.read_text(encoding="utf-8")
        command = OPENCODE_COMMAND.read_text(encoding="utf-8")
        self.assertLessEqual(len([line for line in skill.splitlines() if line.strip()]), 22)
        self.assertLessEqual(len([line for line in command.splitlines() if line.strip()]), 10)
        for body in (skill, command):
            self.assertNotIn("## Agent self-review", body)
            self.assertNotIn("check-update", body)
            self.assertNotIn("adapters/generic.md", body)

    def test_workflow_owns_completion_and_abstention(self) -> None:
        body = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ABSTAINED", body)
        self.assertIn("## 2. 默认继续与完成", body)
        self.assertIn("真正的停止边界", body)
        self.assertIn("不要在第一次实现后", body)

    def test_current_docs_do_not_advertise_adapter_selection(self) -> None:
        readme = README.read_text(encoding="utf-8")
        adoption = ADOPTION.read_text(encoding="utf-8")
        self.assertNotIn("可选\n`adapters/`", readme)
        self.assertNotIn("可选\n`adapters/`", adoption)
        self.assertNotIn("加载 `/TheMasterplan` Skill 时会只读检测", adoption)

    def test_state_doc_removes_adapter_from_v5_selection(self) -> None:
        body = STATE_DOC.read_text(encoding="utf-8")
        self.assertIn("v5 删除 Adapter 抽象", body)
        example = body.split("## v5 变化", 1)[0]
        self.assertNotIn('"adapter"', example)


if __name__ == "__main__":
    unittest.main()
