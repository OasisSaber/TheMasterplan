#!/usr/bin/env python3
"""Regression tests for executor state hygiene and legacy bytecode entries."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR_DIR))

from tmlib.apply import apply_adopt  # noqa: E402
from tmlib.doctor import doctor  # noqa: E402
from tmlib.inspect import detect_status  # noqa: E402
from tmlib.planning import plan_adopt  # noqa: E402
from tmlib.source import resolve_local  # noqa: E402
from tmlib.update import apply_update, plan_update  # noqa: E402
from tmlib.util import (  # noqa: E402
    is_volatile_executor_artifact,
    read_json,
    sha256_of_file,
    write_json_atomic,
)
from tmlib.verify import verify  # noqa: E402

TEST_COMMIT = "a" * 40
VOLATILE_DESTINATION = (
    ".themasterplan/bin/tmlib/__pycache__/update.cpython-311.pyc"
)
NONVOLATILE_DESTINATION = ".themasterplan/bin/tmlib/unexpected.cache"


class ExecutorStateHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.project)],
            check=True,
            capture_output=True,
        )
        self.source = resolve_local(ROOT, commit=TEST_COMMIT)
        self._adopt()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _adopt(self) -> None:
        plan = plan_adopt(
            self.project,
            self.source,
            profile="git",
            validation_path="scripts/check.sh",
        )
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        plan_path = self.project / ".themasterplan-adopt-plan.json"
        write_json_atomic(plan_path, plan)
        apply_adopt(self.project, plan_path, self.source)

    def _state(self) -> dict:
        return read_json(self.project / ".themasterplan/state.json")

    def _write_state(self, state: dict) -> None:
        write_json_atomic(self.project / ".themasterplan/state.json", state)

    def test_volatile_executor_artifact_predicate_is_narrow(self) -> None:
        self.assertTrue(
            is_volatile_executor_artifact(
                ".themasterplan/bin/__pycache__/themasterplan.cpython-311.pyc"
            )
        )
        self.assertTrue(
            is_volatile_executor_artifact(VOLATILE_DESTINATION)
        )
        self.assertTrue(
            is_volatile_executor_artifact(".themasterplan/bin/tmlib/update.pyo")
        )
        self.assertFalse(
            is_volatile_executor_artifact(".themasterplan/bin/tmlib/update.py")
        )
        self.assertFalse(
            is_volatile_executor_artifact("cache/module.pyc")
        )
        self.assertFalse(
            is_volatile_executor_artifact(NONVOLATILE_DESTINATION)
        )

    def test_legacy_bytecode_entries_are_ignored(self) -> None:
        state = self._state()
        state["managed_files"][VOLATILE_DESTINATION] = {
            "source": "<executor>:tmlib/__pycache__/update.cpython-311.pyc",
            "source_sha256": "b" * 64,
            "installed_sha256": "b" * 64,
            "ownership": "managed-replace",
        }
        self._write_state(state)

        verification = verify(self.project)
        diagnostics = doctor(self.project)
        status, issues = detect_status(
            self.project,
            target_version=self.source.version,
        )

        self.assertTrue(verification["ok"], verification["issues"])
        self.assertTrue(diagnostics["ok"], diagnostics["issues"])
        self.assertEqual(status, "CURRENT", issues)
        self.assertEqual(issues, [])

    def test_nonvolatile_executor_entries_remain_checked(self) -> None:
        state = self._state()
        state["managed_files"][NONVOLATILE_DESTINATION] = {
            "source": "<executor>:tmlib/unexpected.cache",
            "source_sha256": "c" * 64,
            "installed_sha256": "c" * 64,
            "ownership": "managed-replace",
        }
        self._write_state(state)

        verification = verify(self.project)
        diagnostics = doctor(self.project)
        status, issues = detect_status(
            self.project,
            target_version=self.source.version,
        )

        self.assertFalse(verification["ok"])
        self.assertFalse(diagnostics["ok"])
        self.assertEqual(status, "BROKEN")
        self.assertTrue(
            any(NONVOLATILE_DESTINATION in issue for issue in issues),
            issues,
        )

    def test_apply_update_rebuilds_state_without_bytecode(self) -> None:
        bytecode = self.project / VOLATILE_DESTINATION
        bytecode.parent.mkdir(parents=True, exist_ok=True)
        bytecode.write_bytes(b"legacy bytecode")

        state = self._state()
        digest = sha256_of_file(bytecode)
        state["managed_files"][VOLATILE_DESTINATION] = {
            "source": "<executor>:tmlib/__pycache__/update.cpython-311.pyc",
            "source_sha256": digest,
            "installed_sha256": digest,
            "ownership": "managed-replace",
        }
        self._write_state(state)

        plan = plan_update(self.project, self.source, state)
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        plan_path = self.project / ".themasterplan-update-plan.json"
        write_json_atomic(plan_path, plan)
        apply_update(self.project, plan_path, self.source)

        updated = self._state()
        managed = updated["managed_files"]
        self.assertNotIn(VOLATILE_DESTINATION, managed)
        self.assertFalse(
            any(
                is_volatile_executor_artifact(relative)
                for relative in managed
            ),
            sorted(managed),
        )

        verification = verify(self.project)
        diagnostics = doctor(self.project)
        status, issues = detect_status(
            self.project,
            target_version=self.source.version,
        )
        self.assertTrue(verification["ok"], verification["issues"])
        self.assertTrue(diagnostics["ok"], diagnostics["issues"])
        self.assertEqual(status, "CURRENT", issues)


if __name__ == "__main__":
    unittest.main()