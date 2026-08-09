"""Contract tests for TheMasterplan v3.1.0 AO + OpenCode adaptation."""

import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OPENCODE_SKILL = ROOT / ".opencode/skills/themasterplan/SKILL.md"
OPENCODE_COMMAND = ROOT / ".opencode/commands/themasterplan.md"
AO_ADAPTER = ROOT / "adapters/agent-orchestrator.md"
AO_EXAMPLE = ROOT / "examples/agent-orchestrator.yaml"
AO_DOC = ROOT / "docs/agent-orchestrator-integration.md"
README = ROOT / "README.md"
MANIFEST = ROOT / "distribution/manifest.json"

LOAD_ORDER_FILES = (
    "AGENTS.md",
    "core/workflow.md",
    "core/policy.md",
    "profiles/git.md",
    "adapters/agent-orchestrator.md",
)
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def read_frontmatter(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"{path}: frontmatter must start with '---'")
    end = next((i for i, line in enumerate(lines[1:], 1) if line == "---"), None)
    if end is None:
        raise AssertionError(f"{path}: frontmatter has no closing '---'")
    data = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(data, dict):
        raise AssertionError(f"{path}: frontmatter must be a mapping")
    return data


class OpenCodeEntryTests(unittest.TestCase):
    def test_skill_frontmatter_matches_opencode_contract(self):
        self.assertTrue(OPENCODE_SKILL.is_file())
        data = read_frontmatter(OPENCODE_SKILL)
        self.assertEqual(data.get("name"), OPENCODE_SKILL.parent.name)
        self.assertRegex(data["name"], SKILL_NAME_RE)
        self.assertIsInstance(data.get("description"), str)
        self.assertTrue(1 <= len(data["description"]) <= 1024)
        self.assertIsInstance(data.get("compatibility"), str)

    def test_command_uses_native_skill_tool_and_arguments(self):
        self.assertTrue(OPENCODE_COMMAND.is_file())
        body = OPENCODE_COMMAND.read_text(encoding="utf-8")
        self.assertIn("native `skill` tool", body)
        self.assertIn("`themasterplan`", body)
        self.assertIn("$ARGUMENTS", body)
        self.assertIn("description", read_frontmatter(OPENCODE_COMMAND))

    def test_entries_stop_when_required_files_are_missing(self):
        for path in (OPENCODE_SKILL, OPENCODE_COMMAND):
            body = path.read_text(encoding="utf-8")
            self.assertIn("required", body.lower())
            self.assertIn("stop", body.lower())

    def test_skill_and_command_declare_complete_load_order(self):
        for path in (OPENCODE_SKILL, OPENCODE_COMMAND):
            body = path.read_text(encoding="utf-8")
            for required in LOAD_ORDER_FILES:
                self.assertIn(required, body, f"{path} omits {required}")


class LegacyEntryTests(unittest.TestCase):
    def test_no_legacy_or_misspelled_opencode_entry(self):
        self.assertFalse((ROOT / ".opencode/skills/aw").exists())
        self.assertFalse((ROOT / ".opencode/commands/aw.md").exists())
        pattern = re.compile(r"themasterplane", re.IGNORECASE)
        for markdown in ROOT.glob(".opencode/**/*.md"):
            self.assertNotRegex(markdown.read_text(encoding="utf-8"), pattern)


class AoAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not AO_ADAPTER.is_file() or not AO_EXAMPLE.is_file():
            raise AssertionError("AO adapter or example configuration is missing")
        cls.adapter = AO_ADAPTER.read_text(encoding="utf-8")
        cls.example = yaml.safe_load(AO_EXAMPLE.read_text(encoding="utf-8"))

    def test_adapter_maps_single_delivery_owner(self):
        self.assertIn("主交付责任人", self.adapter)
        self.assertIn("一个活跃 worker", self.adapter)

    def test_adapter_uses_current_config_model(self):
        self.assertIn("扁平结构", self.adapter)
        self.assertIn("全局 registry", self.adapter)
        self.assertIn("顶层 `projects:`", self.adapter)

    def test_adapter_states_current_auto_merge_semantics(self):
        self.assertIn("保留的 merge intent", self.adapter)
        self.assertIn("按通知路径处理", self.adapter)
        self.assertIn("TheMasterplan 仍明确禁止", self.adapter)
        self.assertNotIn("会在审批通过且 CI 绿色后自动 merge", self.adapter)
        self.assertNotIn("auto: true` 配置无效", self.adapter)

    def test_adapter_corrects_ao_default_agent(self):
        self.assertIn("AO 产品默认", self.adapter)
        self.assertIn("claude-code", self.adapter)
        self.assertIn("opencode", self.adapter)

    def test_example_does_not_reference_legacy_wrapped_schema(self):
        self.assertNotIn(
            "$schema",
            self.example,
            "flat AO project-local config must not reference the legacy "
            "top-level projects-wrapper schema",
        )

    def test_example_is_flat_local_project_config(self):
        self.assertNotIn("projects", self.example)
        for identity_key in ("path", "projectId", "storageKey", "originUrl"):
            self.assertNotIn(identity_key, self.example)
        self.assertEqual(self.example["agent"], "opencode")
        self.assertEqual(self.example["runtime"], "process")
        self.assertEqual(self.example["workspace"], "worktree")
        self.assertEqual(self.example["agentRulesFile"], "AGENTS.md")

    def test_example_uses_opencode_process_worktree(self):
        self.assertEqual(self.example["agent"], "opencode")
        self.assertEqual(self.example["runtime"], "process")
        self.assertEqual(self.example["workspace"], "worktree")

    def test_example_reaction_safety(self):
        reactions = self.example["reactions"]
        self.assertEqual(
            reactions["ci-failed"],
            {"auto": True, "action": "send-to-agent", "retries": 2},
        )
        self.assertEqual(
            reactions["changes-requested"],
            {
                "auto": True,
                "action": "send-to-agent",
                "retries": 2,
                "escalateAfter": "30m",
            },
        )
        self.assertEqual(
            reactions["approved-and-green"],
            {"auto": False, "action": "notify", "priority": "action"},
        )


class DocumentationTruthTests(unittest.TestCase):
    def test_pending_smoke_is_not_called_verified(self):
        docs = AO_DOC.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        premature_status = re.compile(
            r"(?:\|\s*`VERIFIED\*`\s*\||^-\s*`VERIFIED\*`：)",
            re.MULTILINE,
        )
        self.assertNotRegex(docs, premature_status)
        self.assertNotRegex(readme, premature_status)
        self.assertIn("Agent Orchestrator + OpenCode + Git worktree | `PARTIAL`", docs)
        self.assertIn("真实 smoke", docs)

    def test_docs_use_current_config_and_merge_semantics(self):
        docs = AO_DOC.read_text(encoding="utf-8")
        self.assertIn("扁平结构", docs)
        self.assertIn("保留的 merge intent", docs)
        self.assertIn("按通知路径处理", docs)
        self.assertNotIn("auto: true` 配置无效", docs)
        self.assertNotIn("会启用自动 merge", docs)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_v311_and_contains_ao_adapter(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["distribution_version"], "v3.1.1")
        self.assertIn("agent-orchestrator", manifest["components"]["adapters"])
        selected = [
            entry
            for entry in manifest["files"]
            if entry["destination"] == "adapters/agent-orchestrator.md"
        ]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["ownership"], "managed-replace")


class LoadOrderTests(unittest.TestCase):
    def test_authoritative_load_order_files_exist(self):
        missing = [name for name in LOAD_ORDER_FILES if not (ROOT / name).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
