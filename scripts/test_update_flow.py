#!/usr/bin/env python3
"""Update-plan/apply and doctor integration tests for TheMasterplan v5.

Uses only local package copies and temporary Git repositories; no live GitHub.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR_DIR))

from tmlib import TheMasterplanError  # noqa: E402
from tmlib.apply import apply_adopt  # noqa: E402
from tmlib.doctor import doctor  # noqa: E402
from tmlib.manifest import load_manifest  # noqa: E402
from tmlib.planning import plan_adopt  # noqa: E402
from tmlib.source import SourceError, resolve_local, resolve_source  # noqa: E402
from tmlib.update import apply_update, plan_update  # noqa: E402
from tmlib.util import read_json, write_json_atomic  # noqa: E402

TEST_COMMIT = "b" * 40


def copy_package() -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    package = Path(tmp.name)
    for sub in ("distribution", "core", "profiles", "skills", "docs"):
        shutil.copytree(
            ROOT / sub,
            package / sub,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    return tmp, package


class ResolveLocalTest(unittest.TestCase):
    def test_resolve_local_and_source(self) -> None:
        source = resolve_local(ROOT, commit=TEST_COMMIT)
        self.assertEqual(source.commit, TEST_COMMIT)
        self.assertEqual(source.repository, "OasisSaber/TheMasterplan")
        self.assertEqual(source.version, "v5.0.0")
        via_source = resolve_source(str(ROOT), commit=TEST_COMMIT)
        self.assertEqual(via_source.package_root, ROOT.resolve())

    def test_bad_commit_is_rejected(self) -> None:
        with self.assertRaises(SourceError):
            resolve_local(ROOT, commit="not-a-sha")


class UpdateFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.project)],
            check=True,
            capture_output=True,
        )
        self.source = resolve_local(ROOT, commit=TEST_COMMIT)
        self.state = self._adopt(self.source)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _adopt(self, source) -> dict:
        plan = plan_adopt(
            self.project,
            source,
            profile="git",
            validation_path="scripts/check.sh",
        )
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        path = self.project / "adopt.json"
        write_json_atomic(path, plan)
        apply_adopt(self.project, path, source)
        return read_json(self.project / ".themasterplan/state.json")

    def test_unchanged_plan(self) -> None:
        plan = plan_update(self.project, self.source, self.state)
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        self.assertEqual(
            {op["classification"] for op in plan["files"]},
            {"UNCHANGED"},
        )
        self.assertNotIn("adapter", plan["selection"])

    def test_safe_update_then_local_modification_stops(self) -> None:
        package_tmp, package = copy_package()
        self.addCleanup(package_tmp.cleanup)
        (package / "core/workflow.md").write_text(
            "# changed upstream workflow\n",
            encoding="utf-8",
        )
        source2 = resolve_local(package, commit="c" * 40)
        plan = plan_update(self.project, source2, self.state)
        workflow = next(
            op for op in plan["files"]
            if op["destination"] == "core/workflow.md"
        )
        self.assertEqual(workflow["classification"], "UPDATE_SAFE")
        self.assertFalse(plan["stop_conditions"])

        path = self.project / "update.json"
        write_json_atomic(path, plan)
        result = apply_update(self.project, path, source2)
        self.assertIn("core/workflow.md", result["written"])

        (self.project / "core/workflow.md").write_text(
            "local edit\n",
            encoding="utf-8",
        )
        state2 = read_json(self.project / ".themasterplan/state.json")
        plan2 = plan_update(self.project, source2, state2)
        workflow2 = next(
            op for op in plan2["files"]
            if op["destination"] == "core/workflow.md"
        )
        self.assertEqual(workflow2["classification"], "LOCAL_MODIFIED")
        self.assertTrue(plan2["stop_conditions"])

        path2 = self.project / "update2.json"
        write_json_atomic(path2, plan2)
        with self.assertRaises(TheMasterplanError):
            apply_update(self.project, path2, source2)
        self.assertEqual(
            (self.project / "core/workflow.md").read_text(encoding="utf-8"),
            "local edit\n",
        )

    def test_add_and_removed_upstream(self) -> None:
        package_tmp, package = copy_package()
        self.addCleanup(package_tmp.cleanup)
        manifest_path = package / "distribution/manifest.json"
        manifest = load_manifest(manifest_path)
        manifest["files"].append(
            {
                "source": "core/extra.md",
                "destination": "core/extra.md",
                "ownership": "managed-replace",
                "required": False,
            }
        )
        manifest["files"] = [
            entry
            for entry in manifest["files"]
            if entry["destination"] != "profiles/git.md"
        ]
        write_json_atomic(manifest_path, manifest)
        (package / "core/extra.md").write_text("extra\n", encoding="utf-8")
        source2 = resolve_local(package, commit="d" * 40)

        plan = plan_update(self.project, source2, self.state)
        operations = {op["destination"]: op for op in plan["files"]}
        self.assertEqual(operations["core/extra.md"]["classification"], "ADD")
        self.assertEqual(
            operations["profiles/git.md"]["classification"],
            "REMOVED_UPSTREAM",
        )
        self.assertFalse(plan["stop_conditions"])

        path = self.project / "update.json"
        write_json_atomic(path, plan)
        result = apply_update(self.project, path, source2)
        self.assertIn("core/extra.md", result["written"])
        self.assertIn("profiles/git.md", result["removed"])
        self.assertFalse((self.project / "profiles/git.md").exists())

    def test_profile_selection_change_fails_closed(self) -> None:
        package_tmp, package = copy_package()
        self.addCleanup(package_tmp.cleanup)
        manifest_path = package / "distribution/manifest.json"
        manifest = load_manifest(manifest_path)
        manifest["components"] = {"profiles": ["jj"]}
        write_json_atomic(manifest_path, manifest)
        source2 = resolve_local(package, commit="e" * 40)
        plan = plan_update(self.project, source2, self.state)
        self.assertTrue(plan["stop_conditions"])
        self.assertIn("selection no longer supported", plan["stop_conditions"][0])

    def test_v4_generic_adapter_is_normalized_out(self) -> None:
        legacy = json.loads(json.dumps(self.state))
        legacy["selection"]["adapter"] = "generic"
        plan = plan_update(self.project, self.source, legacy)
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        self.assertNotIn("adapter", plan["selection"])

    def test_unknown_legacy_adapter_fails_closed(self) -> None:
        legacy = json.loads(json.dumps(self.state))
        legacy["selection"]["adapter"] = "unknown-orchestrator"
        plan = plan_update(self.project, self.source, legacy)
        self.assertTrue(plan["stop_conditions"])
        self.assertIn("selection no longer supported by v5", plan["stop_conditions"][0])


class DoctorTest(unittest.TestCase):
    def test_absent_and_adopted_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(doctor(root)["ok"])
            subprocess.run(
                ["git", "init", "--initial-branch=main", "-q", str(root)],
                check=True,
                capture_output=True,
            )
            source = resolve_local(ROOT, commit=TEST_COMMIT)
            plan = plan_adopt(
                root,
                source,
                profile="git",
                validation_path="scripts/check.sh",
            )
            path = root / "plan.json"
            write_json_atomic(path, plan)
            apply_adopt(root, path, source)
            self.assertTrue(doctor(root)["ok"])

    def test_modified_managed_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(
                ["git", "init", "--initial-branch=main", "-q", str(root)],
                check=True,
                capture_output=True,
            )
            source = resolve_local(ROOT, commit=TEST_COMMIT)
            plan = plan_adopt(
                root,
                source,
                profile="git",
                validation_path="scripts/check.sh",
            )
            path = root / "plan.json"
            write_json_atomic(path, plan)
            apply_adopt(root, path, source)
            (root / "core/policy.md").write_text("tampered\n", encoding="utf-8")
            report = doctor(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any("hash mismatch" in item for item in report["issues"]))


if __name__ == "__main__":
    unittest.main()
