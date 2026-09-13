#!/usr/bin/env python3
"""Core executor tests for TheMasterplan v5.

Exercises path safety, manifest validation, inspect status, adoption/apply
atomicity, managed-block ownership, rendered consumer workflow, custom
validation paths, and the adapter-free CLI surface against temporary repos.
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

from themasterplan import build_parser  # noqa: E402
from tmlib import TheMasterplanError, PathSafetyError  # noqa: E402
from tmlib.apply import apply_adopt  # noqa: E402
from tmlib.inspect import detect_status, inspect  # noqa: E402
from tmlib.manifest import ManifestError, load_manifest  # noqa: E402
from tmlib.planning import plan_adopt  # noqa: E402
from tmlib.source import read_package_file, resolve_local  # noqa: E402
from tmlib.util import safe_join, sha256_of_file, write_json_atomic  # noqa: E402
from tmlib.verify import verify  # noqa: E402

TEST_COMMIT = "a" * 40
MANIFEST_VERSION = load_manifest(ROOT / "distribution/manifest.json")[
    "distribution_version"
]


def run_exec(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EXECUTOR_DIR / "themasterplan.py"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


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


class PathSafetyTest(unittest.TestCase):
    def test_rejects_parent_and_absolute_paths(self) -> None:
        with self.assertRaises(PathSafetyError):
            safe_join(Path("/tmp/root"), "../escape")
        with self.assertRaises(PathSafetyError):
            safe_join(Path("/tmp/root"), "/etc/passwd")
        self.assertTrue(
            safe_join(Path("/tmp/root"), "core/policy.md")
            .as_posix()
            .endswith("core/policy.md")
        )


class ManifestTest(unittest.TestCase):
    def test_real_manifest_loads_and_has_no_adapter_component(self) -> None:
        manifest = load_manifest(ROOT / "distribution/manifest.json")
        self.assertEqual(manifest["distribution_version"], "v5.0.0")
        self.assertNotIn("adapters", manifest.get("components", {}))
        self.assertTrue(manifest["files"])

    def test_invalid_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"files": []}', encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(path)

    def test_duplicate_and_unsafe_destinations_are_rejected(self) -> None:
        base = {
            "schema_version": 1,
            "distribution_version": "v5.0.0",
            "source_repository": "OasisSaber/TheMasterplan",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            duplicate = root / "duplicate.json"
            duplicate.write_text(
                json.dumps(
                    {
                        **base,
                        "files": [
                            {"source": "a", "destination": "dup", "ownership": "managed-replace"},
                            {"source": "b", "destination": "dup", "ownership": "managed-replace"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ManifestError):
                load_manifest(duplicate)

            unsafe = root / "unsafe.json"
            unsafe.write_text(
                json.dumps(
                    {
                        **base,
                        "files": [
                            {"source": "a", "destination": "../escape", "ownership": "managed-replace"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ManifestError):
                load_manifest(unsafe)


class InspectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_absent_and_incomplete(self) -> None:
        self.assertEqual(detect_status(self.root)[0], "ABSENT")
        (self.root / "core").mkdir()
        (self.root / "core/policy.md").write_text("x", encoding="utf-8")
        self.assertEqual(detect_status(self.root)[0], "INCOMPLETE")

    def test_current_modified_and_outdated(self) -> None:
        (self.root / "core").mkdir()
        for name in ("policy.md", "workflow.md"):
            (self.root / "core" / name).write_text("body", encoding="utf-8")
        state = {
            "schema_version": 1,
            "source": {
                "repository": "OasisSaber/TheMasterplan",
                "version": MANIFEST_VERSION,
                "commit": TEST_COMMIT,
            },
            "selection": {
                "profile": "git",
                "validation_path": "scripts/check.sh",
                "default_branch": "main",
            },
            "managed_files": {
                relative: {
                    "installed_sha256": sha256_of_file(self.root / relative),
                    "ownership": "managed-replace",
                }
                for relative in ("core/policy.md", "core/workflow.md")
            },
        }
        write_json_atomic(self.root / ".themasterplan/state.json", state)
        self.assertEqual(detect_status(self.root)[0], "CURRENT")
        self.assertEqual(
            detect_status(self.root, target_version="v9.9.9")[0],
            "OUTDATED",
        )
        (self.root / "core/policy.md").write_text("changed", encoding="utf-8")
        self.assertEqual(
            detect_status(self.root, target_version="v9.9.9")[0],
            "MODIFIED",
        )

    def test_inspect_reports_profile_not_adapter(self) -> None:
        (self.root / ".jj").mkdir()
        (self.root / ".trellis").mkdir()
        result = inspect(self.root)
        self.assertEqual(result["detected_profile"], "jj")
        self.assertNotIn("detected_adapter", result)


class AdoptFlowTest(unittest.TestCase):
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

    def _plan(
        self,
        *,
        profile: str = "git",
        validation: str = "scripts/check.sh",
        default_branch: str = "main",
    ) -> dict:
        return plan_adopt(
            self.project,
            self.source,
            profile=profile,
            validation_path=validation,
            default_branch=default_branch,
        )

    def _apply(self, plan: dict) -> dict:
        path = self.project / "plan.json"
        write_json_atomic(path, plan)
        return apply_adopt(self.project, path, self.source)

    def test_full_adopt_verify_and_idempotent(self) -> None:
        plan = self._plan()
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        destinations = {op["destination"] for op in plan["files"]}
        self.assertIn("core/policy.md", destinations)
        self.assertIn("core/workflow.md", destinations)
        self.assertIn("docs/client-update-flow.md", destinations)
        self.assertIn("skills/themasterplan/references/jj-lifecycle.md", destinations)
        self.assertIn("AGENTS.md", destinations)
        self.assertFalse(any(path.startswith("adapters/") for path in destinations))

        first = self._apply(plan)
        self.assertTrue((self.project / ".themasterplan/state.json").is_file())
        self.assertTrue((self.project / ".themasterplan/bin/themasterplan.py").is_file())
        state = json.loads(
            (self.project / ".themasterplan/state.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("adapter", state["selection"])
        self.assertTrue(verify(self.project)["ok"])

        second = self._apply(plan)
        self.assertEqual(second["written"], [])
        self.assertEqual(second["unchanged"], first["written"])
        self.assertEqual(
            detect_status(self.project, target_version=MANIFEST_VERSION)[0],
            "CURRENT",
        )

    def test_existing_agents_content_outside_block_is_preserved(self) -> None:
        agents = self.project / "AGENTS.md"
        agents.write_text(
            "PROJECT HEADER\n<!-- THEMASTERPLAN:BEGIN MANAGED -->old<!-- THEMASTERPLAN:END MANAGED -->\nPROJECT FOOTER\n",
            encoding="utf-8",
        )
        plan = self._plan()
        operation = next(op for op in plan["files"] if op["destination"] == "AGENTS.md")
        self.assertEqual(operation["classification"], "BLOCK_PRESENT")
        self._apply(plan)
        body = agents.read_text(encoding="utf-8")
        self.assertTrue(body.startswith("PROJECT HEADER"))
        self.assertTrue(body.rstrip().endswith("PROJECT FOOTER"))
        self.assertNotIn("old", body)

    def test_managed_block_tamper_is_detected(self) -> None:
        self._apply(self._plan())
        agents = self.project / "AGENTS.md"
        data = agents.read_bytes()
        self.assertIn(b"This block is the project Context Router.", data)
        agents.write_bytes(
            data.replace(
                b"This block is the project Context Router.",
                b"This managed block was tampered.",
                1,
            )
        )
        self.assertEqual(detect_status(self.project)[0], "MODIFIED")
        self.assertFalse(verify(self.project)["ok"])

    def test_target_change_after_plan_stops(self) -> None:
        (self.project / "core").mkdir(parents=True)
        (self.project / "core/workflow.md").write_bytes(
            read_package_file(ROOT, "core/workflow.md")
        )
        plan = self._plan()
        path = self.project / "plan.json"
        write_json_atomic(path, plan)
        (self.project / "core/workflow.md").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(TheMasterplanError):
            apply_adopt(self.project, path, self.source)
        self.assertFalse((self.project / ".themasterplan/state.json").exists())

    def test_source_change_after_plan_stops_before_any_write(self) -> None:
        package_tmp, package = copy_package()
        self.addCleanup(package_tmp.cleanup)
        source = resolve_local(package, commit=TEST_COMMIT)
        plan = plan_adopt(
            self.project,
            source,
            profile="git",
            validation_path="scripts/check.sh",
        )
        path = self.project / "plan.json"
        write_json_atomic(path, plan)
        (package / "profiles/git.md").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(TheMasterplanError):
            apply_adopt(self.project, path, source)
        self.assertFalse((self.project / "core/workflow.md").exists())
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".themasterplan/state.json").exists())

    def test_jj_profile_and_custom_rendering(self) -> None:
        plan = self._plan(
            profile="jj",
            validation="tools/verify.sh",
            default_branch="master",
        )
        destinations = {op["destination"] for op in plan["files"]}
        self.assertIn("profiles/jj.md", destinations)
        self.assertNotIn("profiles/git.md", destinations)
        self.assertIn("tools/verify.sh", destinations)
        self._apply(plan)
        workflow = (self.project / ".github/workflows/check.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(workflow.count('branches: ["master"]'), 2)
        self.assertIn('project-check-path: "tools/verify.sh"', workflow)


class CliTest(unittest.TestCase):
    def test_inspect_absent_and_adopt_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                run_exec(["inspect", "--root", str(root)], root).returncode,
                0,
            )
            plan = root / "plan.json"
            process = run_exec(
                [
                    "plan-adopt",
                    "--root", str(root),
                    "--source", str(ROOT),
                    "--commit", TEST_COMMIT,
                    "--profile", "git",
                    "--validation-path", "scripts/check.sh",
                    "--output", str(plan),
                ],
                root,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            applied = run_exec(
                [
                    "apply-adopt",
                    "--root", str(root),
                    "--plan", str(plan),
                    "--source", str(ROOT),
                    "--commit", TEST_COMMIT,
                ],
                root,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(
                run_exec(["verify", "--root", str(root)], root).returncode,
                0,
            )

    def test_plan_adopt_has_no_adapter_argument(self) -> None:
        parser = build_parser()
        common = [
            "plan-adopt",
            "--source", ".",
            "--profile", "git",
            "--validation-path", "scripts/check.sh",
            "--output", "plan.json",
        ]
        args = parser.parse_args(common)
        self.assertFalse(hasattr(args, "adapter"))
        with self.assertRaises(SystemExit):
            parser.parse_args(common + ["--adapter", "generic"])


if __name__ == "__main__":
    unittest.main()
