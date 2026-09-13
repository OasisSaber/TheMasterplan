#!/usr/bin/env python3
"""v4 generic Adapter -> v5 adapter-free migration tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR))

from tmlib import TheMasterplanError  # noqa: E402
from tmlib.apply import apply_adopt  # noqa: E402
from tmlib.planning import plan_adopt  # noqa: E402
from tmlib.source import resolve_local  # noqa: E402
from tmlib.update import apply_update, plan_update  # noqa: E402
from tmlib.util import read_json, sha256_of_file, write_json_atomic  # noqa: E402

TARGET_COMMIT = "5" * 40
OLD_COMMIT = "4" * 40


class V5AdapterMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.project)],
            check=True,
            capture_output=True,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _target_source(self):
        return resolve_local(ROOT, commit=TARGET_COMMIT)

    def _adopt_v5_then_mark_as_v4(self) -> dict:
        source = self._target_source()
        plan = plan_adopt(
            self.project,
            source,
            profile="git",
            validation_path="scripts/check.sh",
        )
        plan_path = self.project / "adopt.json"
        write_json_atomic(plan_path, plan)
        apply_adopt(self.project, plan_path, source)

        state_path = self.project / ".themasterplan/state.json"
        state = read_json(state_path)
        state["source"] = {
            "repository": "OasisSaber/TheMasterplan",
            "version": "v4.1.0",
            "commit": OLD_COMMIT,
        }
        state["selection"]["adapter"] = "generic"
        return state

    def _add_legacy_adapter(self, state: dict) -> Path:
        adapter = self.project / "adapters/generic.md"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text("legacy generic adapter\n", encoding="utf-8")
        installed = sha256_of_file(adapter)
        state["managed_files"]["adapters/generic.md"] = {
            "source": "adapters/generic.md",
            "source_sha256": installed,
            "installed_sha256": installed,
            "ownership": "managed-replace",
        }
        write_json_atomic(self.project / ".themasterplan/state.json", state)
        return adapter

    def test_clean_v4_generic_adapter_is_removed_and_selection_normalized(self) -> None:
        state = self._adopt_v5_then_mark_as_v4()
        adapter = self._add_legacy_adapter(state)
        source = self._target_source()

        plan = plan_update(self.project, source, state)
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        self.assertNotIn("adapter", plan["selection"])
        adapter_op = next(
            op for op in plan["files"]
            if op["destination"] == "adapters/generic.md"
        )
        self.assertEqual(adapter_op["classification"], "REMOVED_UPSTREAM")

        plan_path = self.project / "update.json"
        write_json_atomic(plan_path, plan)
        result = apply_update(self.project, plan_path, source)

        self.assertIn("adapters/generic.md", result["removed"])
        self.assertFalse(adapter.exists())
        final_state = read_json(self.project / ".themasterplan/state.json")
        self.assertNotIn("adapter", final_state["selection"])
        self.assertNotIn("adapters/generic.md", final_state["managed_files"])

    def test_locally_modified_legacy_adapter_fails_closed_without_deletion(self) -> None:
        state = self._adopt_v5_then_mark_as_v4()
        adapter = self._add_legacy_adapter(state)
        adapter.write_text("locally modified legacy adapter\n", encoding="utf-8")
        source = self._target_source()

        plan = plan_update(self.project, source, state)
        adapter_op = next(
            op for op in plan["files"]
            if op["destination"] == "adapters/generic.md"
        )
        self.assertEqual(adapter_op["classification"], "LOCAL_MODIFIED")
        self.assertTrue(plan["stop_conditions"])

        before = adapter.read_bytes()
        plan_path = self.project / "update.json"
        write_json_atomic(plan_path, plan)
        with self.assertRaises(TheMasterplanError):
            apply_update(self.project, plan_path, source)
        self.assertEqual(adapter.read_bytes(), before)

    def test_unknown_legacy_adapter_fails_closed(self) -> None:
        state = self._adopt_v5_then_mark_as_v4()
        state["selection"]["adapter"] = "external-orchestrator"
        source = self._target_source()
        plan = plan_update(self.project, source, state)
        self.assertTrue(plan["stop_conditions"])
        self.assertIn("selection no longer supported by v5", plan["stop_conditions"][0])


if __name__ == "__main__":
    unittest.main()
