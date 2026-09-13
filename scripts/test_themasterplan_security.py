#!/usr/bin/env python3
"""Regression tests for the TheMasterplan security review fixes."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = REPO_ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR_DIR))

from tmlib.doctor import doctor  # noqa: E402
from tmlib.source import (  # noqa: E402
    SourceError,
    resolve_local,
    resolve_remote,
)
from tmlib.update import (  # noqa: E402
    UpdateError,
    _validate_update_plan,
    apply_update,
    plan_update,
)
from tmlib.util import sha256_of_file, write_json_atomic  # noqa: E402

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
SHA256_A = "1" * 64


def copy_package() -> Path:
    destination = Path(tempfile.mkdtemp(prefix="themasterplan-package-"))
    for relative in (
        "distribution",
        "core",
        "profiles",
        "skills/themasterplan",
        "docs/client-update-flow.md",
    ):
        source = REPO_ROOT / relative
        if not source.exists():
            raise RuntimeError(f"missing test source: {source}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return destination


def make_archive(package_root: Path) -> Path:
    temporary = Path(tempfile.mkdtemp(prefix="themasterplan-archive-"))
    archive = temporary / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(package_root.rglob("*")):
            if not path.is_file():
                continue
            relative = Path("TheMasterplan-source") / path.relative_to(package_root)
            data = path.read_bytes()
            info = tarfile.TarInfo(relative.as_posix())
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
    return archive


class SourceIdentityTest(unittest.TestCase):
    def test_sha_ref_and_explicit_commit_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SourceError):
                resolve_remote(
                    "OasisSaber/TheMasterplan",
                    COMMIT_A,
                    Path(temporary),
                    commit=COMMIT_B,
                )

    def test_tag_archive_and_cache_are_commit_addressed(self) -> None:
        package = copy_package()
        self.addCleanup(shutil.rmtree, package, True)
        archive = make_archive(package)
        self.addCleanup(shutil.rmtree, archive.parent, True)
        captured: dict[str, object] = {}

        def fake_download(url: str, cache_path: Path, timeout: int = 45) -> Path:
            captured["url"] = url
            captured["cache_path"] = cache_path
            return archive

        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch(
                "tmlib.source._resolve_tag_commit",
                return_value=COMMIT_B,
            ), mock.patch(
                "tmlib.source._download_archive",
                side_effect=fake_download,
            ):
                resolved = resolve_remote(
                    "OasisSaber/TheMasterplan",
                    json.loads((package / "distribution" / "manifest.json").read_text(encoding="utf-8"))["distribution_version"],
                    Path(temporary),
                )

        self.assertEqual(resolved.commit, COMMIT_B)
        self.assertIn(COMMIT_B, str(captured["url"]))
        self.assertNotIn("v3.0.0", str(captured["cache_path"]))
        self.assertIn(COMMIT_B, str(captured["cache_path"]))

    def test_manifest_repository_mismatch_is_rejected(self) -> None:
        package = copy_package()
        self.addCleanup(shutil.rmtree, package, True)
        manifest_path = package / "distribution" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_repository"] = "OtherOwner/OtherRepo"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        archive = make_archive(package)
        self.addCleanup(shutil.rmtree, archive.parent, True)

        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch(
                "tmlib.source._download_archive",
                return_value=archive,
            ):
                with self.assertRaises(SourceError):
                    resolve_remote(
                        "OasisSaber/TheMasterplan",
                        COMMIT_B,
                        Path(temporary),
                    )


class UpdateSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        self.package = copy_package()
        self.source = resolve_local(self.package, commit=COMMIT_B)

    def tearDown(self) -> None:
        shutil.rmtree(self.package, ignore_errors=True)
        self.temporary.cleanup()

    def _state_with_policy(self) -> dict:
        source_policy = self.package / "core" / "policy.md"
        target_policy = self.project / "core" / "policy.md"
        target_policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_policy, target_policy)
        return {
            "schema_version": 1,
            "source": self.source.as_dict(),
            "selection": {
                "profile": "git",
                "adapter": "generic",
                "validation_path": "scripts/check.sh",
                "default_branch": "main",
            },
            "managed_files": {
                "core/policy.md": {
                    "source": "core/policy.md",
                    "source_sha256": sha256_of_file(source_policy),
                    "installed_sha256": sha256_of_file(target_policy),
                    "ownership": "managed-replace",
                }
            },
        }

    def test_unchanged_target_changed_after_plan_is_rejected(self) -> None:
        state = self._state_with_policy()
        plan = plan_update(self.project, self.source, state)
        policy = next(
            operation
            for operation in plan["files"]
            if operation["destination"] == "core/policy.md"
        )
        self.assertEqual(policy["classification"], "UNCHANGED")

        plan_path = self.project / "plan.json"
        write_json_atomic(plan_path, plan)
        (self.project / "core" / "policy.md").write_text(
            "tampered after planning\n",
            encoding="utf-8",
        )

        with self.assertRaises(UpdateError):
            apply_update(self.project, plan_path, self.source)
        self.assertFalse(
            (self.project / "profiles" / "git.md").exists(),
            "precondition failure must occur before ADD writes",
        )

    def test_update_installs_executor_from_target_source(self) -> None:
        target_exec = (
            self.package
            / "skills"
            / "themasterplan"
            / "scripts"
            / "themasterplan.py"
        )
        target_exec.write_text(
            target_exec.read_text(encoding="utf-8")
            + "\n# target-version-marker\n",
            encoding="utf-8",
        )

        old_exec = self.project / ".themasterplan" / "bin" / "themasterplan.py"
        old_exec.parent.mkdir(parents=True, exist_ok=True)
        old_exec.write_text("# old-executor\n", encoding="utf-8")

        for relative in ("core/policy.md", "core/workflow.md"):
            target = self.project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("present\n", encoding="utf-8")
        validation = self.project / "scripts" / "check.sh"
        validation.parent.mkdir(parents=True, exist_ok=True)
        validation.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

        managed_files = {}
        for relative in ("core/policy.md", "core/workflow.md"):
            source_file = self.package / relative
            target_file = self.project / relative
            digest = sha256_of_file(target_file)
            managed_files[relative] = {
                "source": relative,
                "source_sha256": sha256_of_file(source_file),
                "installed_sha256": digest,
                "ownership": "managed-replace",
            }
        old_state = {
            "schema_version": 1,
            "source": {
                "repository": self.source.repository,
                "version": self.source.version,
                "commit": COMMIT_A,
            },
            "selection": {
                "profile": "git",
                "adapter": "generic",
                "validation_path": "scripts/check.sh",
                "default_branch": "main",
            },
            "managed_files": managed_files,
        }
        plan = plan_update(self.project, self.source, old_state)
        plan_path = self.project / "executor-plan.json"
        write_json_atomic(plan_path, plan)
        apply_update(self.project, plan_path, self.source)

        self.assertEqual(old_exec.read_bytes(), target_exec.read_bytes())
        state = json.loads(
            (self.project / ".themasterplan" / "state.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("adapter", state["selection"])
        self.assertIn(".themasterplan/bin/tmlib/source.py", state["managed_files"])

        installed_source = self.project / ".themasterplan" / "bin" / "tmlib" / "source.py"
        installed_source.write_text("# tampered\n", encoding="utf-8")
        report = doctor(self.project)
        self.assertTrue(
            any(
                "hash mismatch" in issue
                and ".themasterplan/bin/tmlib/source.py" in issue
                for issue in report["issues"]
            ),
            report,
        )

    def test_duplicate_update_destination_is_rejected(self) -> None:
        operation = {
            "source": "core/policy.md",
            "destination": "core/policy.md",
            "ownership": "managed-replace",
            "classification": "UNCHANGED",
            "source_sha256": SHA256_A,
            "observed_sha256": SHA256_A,
        }
        plan = {
            "schema_version": 1,
            "plan_type": "update",
            "source": self.source.as_dict(),
            "selection": {},
            "files": [operation, dict(operation)],
            "stop_conditions": [],
        }
        with self.assertRaises(UpdateError):
            _validate_update_plan(plan)


if __name__ == "__main__":
    unittest.main()
