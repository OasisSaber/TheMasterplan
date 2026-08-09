#!/usr/bin/env python3
"""Release-integrity regression tests for TheMasterplan v3.1.1.

These tests focus on the installed executor artifact and the v3.1.0 -> v3.1.1
bridge. They intentionally avoid live GitHub requests.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR_DIR))

from awlib.apply import EXECUTOR_FILES, apply_adopt  # noqa: E402
from awlib.manifest import load_manifest  # noqa: E402
from awlib.planning import plan_adopt  # noqa: E402
from awlib.source import resolve_local  # noqa: E402
from awlib.update import apply_update, plan_update  # noqa: E402
from awlib.update_check import ReleaseIdentity, check_update  # noqa: E402
from awlib.util import read_json, write_json_atomic  # noqa: E402
from awlib.verify import verify  # noqa: E402

TEST_COMMIT = "a" * 40
OLD_COMMIT = "c" * 40
OTHER_COMMIT = "b" * 40
REPOSITORY = "OasisSaber/TheMasterplan"
BRIDGE_DESTINATION = ".aw/bin/awlib/update_check.py"
BRIDGE_SOURCE = "skills/themasterplan/scripts/awlib/update_check.py"


class ReleaseIdentityTests(unittest.TestCase):
    def test_release_identity_serializes_repository(self) -> None:
        identity = ReleaseIdentity(
            repository=REPOSITORY,
            version="v3.1.1",
            commit=TEST_COMMIT,
        )
        self.assertEqual(
            identity.to_dict(),
            {
                "repository": REPOSITORY,
                "version": "v3.1.1",
                "commit": TEST_COMMIT,
            },
        )

    def test_same_version_different_commit_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".aw/cache").mkdir(parents=True)
            write_json_atomic(
                project / ".aw/state.json",
                {
                    "schema_version": 1,
                    "source": {
                        "repository": REPOSITORY,
                        "version": "v3.1.1",
                        "commit": TEST_COMMIT,
                    },
                },
            )
            write_json_atomic(
                project / ".aw/cache/update-check.json",
                {
                    "checked_at": time.time(),
                    "repository": REPOSITORY,
                    "include_prerelease": False,
                    "latest": {
                        "version": "v3.1.1",
                        "commit": OTHER_COMMIT,
                    },
                },
            )

            result = check_update(project, use_cache=True)

        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["recommended_next_step"], "continue")
        self.assertTrue(result["cache_used"])


class DistributionContractTests(unittest.TestCase):
    def test_manifest_is_v311_and_contains_executor_bridge(self) -> None:
        manifest = load_manifest(ROOT / "distribution/manifest.json")
        self.assertEqual(manifest["distribution_version"], "v3.1.1")

        bridges = [
            entry
            for entry in manifest["files"]
            if entry["destination"] == BRIDGE_DESTINATION
        ]
        self.assertEqual(len(bridges), 1)
        self.assertEqual(bridges[0]["source"], BRIDGE_SOURCE)
        self.assertEqual(bridges[0]["ownership"], "managed-replace")
        self.assertTrue(bridges[0]["required"])

    def test_executor_bundle_contains_update_check(self) -> None:
        self.assertIn("awlib/update_check.py", EXECUTOR_FILES)


class InstalledExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.project)],
            check=True,
            capture_output=True,
        )
        self.source = resolve_local(ROOT, commit=TEST_COMMIT)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _adopt(self) -> None:
        plan = plan_adopt(
            self.project,
            self.source,
            profile="git",
            adapter="generic",
            validation_path="scripts/check.sh",
        )
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        plan_path = self.project / ".aw-adopt-plan.json"
        write_json_atomic(plan_path, plan)
        apply_adopt(self.project, plan_path, self.source)

    def _assert_installed_executor_starts(self) -> None:
        installed = self.project / ".aw/bin/aw.py"
        module = self.project / BRIDGE_DESTINATION
        self.assertTrue(installed.is_file())
        self.assertTrue(module.is_file())

        process = subprocess.run(
            [sys.executable, str(installed), "--help"],
            cwd=str(self.project),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)

        report = verify(self.project)
        self.assertTrue(report["ok"], report["issues"])

    def test_fresh_adoption_installs_runnable_executor(self) -> None:
        self._adopt()
        self._assert_installed_executor_starts()

    def test_v310_state_plans_bridge_as_add(self) -> None:
        """Prove the bridge appears as a normal ADD operation."""
        self._adopt()

        bridge = self.project / BRIDGE_DESTINATION
        bridge.unlink()

        state_path = self.project / ".aw/state.json"
        state = read_json(state_path)
        state["source"] = {
            "repository": REPOSITORY,
            "version": "v3.1.0",
            "commit": OLD_COMMIT,
        }
        state["managed_files"].pop(BRIDGE_DESTINATION, None)
        write_json_atomic(state_path, state)

        plan = plan_update(self.project, self.source, state)
        bridge_operation = next(
            operation
            for operation in plan["files"]
            if operation["destination"] == BRIDGE_DESTINATION
        )
        self.assertEqual(bridge_operation["classification"], "ADD")
        self.assertEqual(bridge_operation["source"], BRIDGE_SOURCE)
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])

        plan_path = self.project / ".aw-update-plan.json"
        write_json_atomic(plan_path, plan)
        apply_update(self.project, plan_path, self.source)

        self._assert_installed_executor_starts()


if __name__ == "__main__":
    unittest.main()
