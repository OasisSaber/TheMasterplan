"""Tests for read-only update detection and its v5 context contract.

Update detection remains a deterministic executor capability, but v5 no longer
runs it on every Skill invocation. These tests cover the status machine,
release filtering, immutable identity, cache behavior, zero-write guarantees,
and the new intent-driven routing contract without live GitHub requests.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = ROOT / "skills" / "themasterplan" / "scripts"
sys.path.insert(0, str(EXECUTOR_DIR))

import tmlib.update_check as check_mod  # noqa: E402
from tmlib.update_check import (  # noqa: E402
    ReleaseIdentity,
    UpdateCheckError,
    check_update,
    compare_versions,
    fetch_latest_stable_release,
    parse_semver,
    read_current_identity,
)

REPOSITORY = "OasisSaber/TheMasterplan"
CURRENT_SHA = "a" * 40
LATEST_SHA = "b" * 40


def state(version: str = "v4.1.0", commit: str = CURRENT_SHA) -> dict:
    return {
        "schema_version": 1,
        "source": {
            "repository": REPOSITORY,
            "version": version,
            "commit": commit,
        },
    }


def write_state(root: Path, version: str = "v4.1.0", commit: str = CURRENT_SHA) -> Path:
    path = root / ".themasterplan/state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state(version, commit)), encoding="utf-8")
    return path


class SemVerTests(unittest.TestCase):
    def test_parse_semver(self) -> None:
        self.assertEqual(parse_semver("v5.0.0"), (5, 0, 0))
        self.assertIsNone(parse_semver("main"))
        self.assertIsNone(parse_semver("v5"))

    def test_compare_versions(self) -> None:
        self.assertEqual(compare_versions("v4.1.0", "v5.0.0"), "UPDATE_AVAILABLE")
        self.assertEqual(compare_versions("v5.0.0", "v5.0.0"), "CURRENT")
        self.assertEqual(compare_versions("v6.0.0", "v5.0.0"), "AHEAD")
        self.assertEqual(compare_versions("main", "v5.0.0"), "UNKNOWN")


class IdentityTests(unittest.TestCase):
    def test_not_adopted_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_current_identity(Path(tmp)))

    def test_valid_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_state(root)
            identity = read_current_identity(root)
        assert identity is not None
        self.assertEqual(identity.repository, REPOSITORY)
        self.assertEqual(identity.version, "v4.1.0")
        self.assertEqual(identity.commit, CURRENT_SHA)

    def test_corrupt_state_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".themasterplan/state.json"
            path.parent.mkdir(parents=True)
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(UpdateCheckError):
                read_current_identity(root)

    def test_invalid_repository_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = state()
            payload["source"]["repository"] = "bad repository"
            path = root / ".themasterplan/state.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(UpdateCheckError):
                read_current_identity(root)


class ReleaseSelectionTests(unittest.TestCase):
    def test_stable_release_filters_draft_prerelease_and_non_semver(self) -> None:
        releases = [
            {"tag_name": "latest", "draft": False, "prerelease": False},
            {"tag_name": "v9.0.0", "draft": True, "prerelease": False},
            {"tag_name": "v6.0.0", "draft": False, "prerelease": True},
            {
                "tag_name": "v5.0.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://example.invalid/v5.0.0",
                "published_at": "2026-09-13T00:00:00Z",
            },
        ]
        with mock.patch.object(
            check_mod,
            "_fetch_releases",
            return_value=json.dumps(releases).encode("utf-8"),
        ), mock.patch.object(
            check_mod,
            "_resolve_tag_commit",
            return_value=LATEST_SHA,
        ):
            release = fetch_latest_stable_release(REPOSITORY)

        self.assertEqual(release.version, "v5.0.0")
        self.assertEqual(release.commit, LATEST_SHA)
        self.assertFalse(release.prerelease)

    def test_include_prerelease_can_select_higher_semver(self) -> None:
        releases = [
            {"tag_name": "v5.0.0", "draft": False, "prerelease": False},
            {"tag_name": "v6.0.0", "draft": False, "prerelease": True},
        ]
        with mock.patch.object(
            check_mod,
            "_fetch_releases",
            return_value=json.dumps(releases).encode("utf-8"),
        ), mock.patch.object(
            check_mod,
            "_resolve_tag_commit",
            return_value=LATEST_SHA,
        ):
            release = fetch_latest_stable_release(
                REPOSITORY,
                include_prerelease=True,
            )
        self.assertEqual(release.version, "v6.0.0")
        self.assertTrue(release.prerelease)

    def test_tag_resolution_failure_is_wrapped(self) -> None:
        releases = [
            {"tag_name": "v5.0.0", "draft": False, "prerelease": False},
        ]
        with mock.patch.object(
            check_mod,
            "_fetch_releases",
            return_value=json.dumps(releases).encode("utf-8"),
        ), mock.patch.object(
            check_mod,
            "_resolve_tag_commit",
            side_effect=check_mod.TheMasterplanError("no tag"),
        ):
            with self.assertRaises(UpdateCheckError):
                fetch_latest_stable_release(REPOSITORY)


class CheckUpdateTests(unittest.TestCase):
    def _run(
        self,
        current_version: str,
        latest_version: str,
        *,
        current_commit: str = CURRENT_SHA,
        latest_commit: str = LATEST_SHA,
    ) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_state(root, current_version, current_commit)
            latest = ReleaseIdentity(
                repository=REPOSITORY,
                version=latest_version,
                commit=latest_commit,
            )
            with mock.patch.object(
                check_mod,
                "fetch_latest_stable_release",
                return_value=latest,
            ):
                return check_update(root, use_cache=False)

    def test_update_available(self) -> None:
        result = self._run("v4.1.0", "v5.0.0")
        self.assertEqual(result["status"], "UPDATE_AVAILABLE")
        self.assertEqual(result["recommended_next_step"], "ask-user")
        self.assertFalse(result["writes_performed"])

    def test_current_requires_same_commit(self) -> None:
        result = self._run(
            "v5.0.0",
            "v5.0.0",
            current_commit=LATEST_SHA,
            latest_commit=LATEST_SHA,
        )
        self.assertEqual(result["status"], "CURRENT")
        self.assertEqual(result["recommended_next_step"], "continue")

    def test_same_version_different_commit_is_unknown(self) -> None:
        result = self._run("v5.0.0", "v5.0.0")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_ahead(self) -> None:
        result = self._run("v6.0.0", "v5.0.0")
        self.assertEqual(result["status"], "AHEAD")

    def test_not_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = check_update(Path(tmp), use_cache=False)
        self.assertEqual(result["status"], "NOT_ADOPTED")
        self.assertFalse(result["writes_performed"])

    def test_remote_failure_is_unavailable_and_state_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = write_state(root)
            before = state_path.read_bytes()
            with mock.patch.object(
                check_mod,
                "fetch_latest_stable_release",
                side_effect=UpdateCheckError("offline"),
            ):
                result = check_update(root, use_cache=False)
            after = state_path.read_bytes()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(before, after)
        self.assertFalse(result["writes_performed"])

    def test_valid_cache_avoids_remote_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_state(root, "v4.1.0", CURRENT_SHA)
            cache = root / ".themasterplan/cache/update-check.json"
            cache.parent.mkdir(parents=True)
            cache.write_text(
                json.dumps(
                    {
                        "checked_at": time.time(),
                        "repository": REPOSITORY,
                        "include_prerelease": False,
                        "latest": {
                            "version": "v5.0.0",
                            "commit": LATEST_SHA,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                check_mod,
                "fetch_latest_stable_release",
                side_effect=AssertionError("remote must not be called"),
            ):
                result = check_update(root, use_cache=True)
        self.assertEqual(result["status"], "UPDATE_AVAILABLE")
        self.assertTrue(result["cache_used"])

    def test_corrupt_cache_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_state(root, "v4.1.0", CURRENT_SHA)
            cache = root / ".themasterplan/cache/update-check.json"
            cache.parent.mkdir(parents=True)
            cache.write_text("{bad", encoding="utf-8")
            latest = ReleaseIdentity(
                repository=REPOSITORY,
                version="v5.0.0",
                commit=LATEST_SHA,
            )
            with mock.patch.object(
                check_mod,
                "fetch_latest_stable_release",
                return_value=latest,
            ):
                result = check_update(root, use_cache=True)
        self.assertEqual(result["status"], "UPDATE_AVAILABLE")
        self.assertNotIn("cache_used", result)


class V5ContextContractTests(unittest.TestCase):
    def test_skill_routes_update_instead_of_embedding_update_workflow(self) -> None:
        skill = (ROOT / "skills/themasterplan/SKILL.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        update_doc = (ROOT / "docs/client-update-flow.md").read_text(encoding="utf-8")

        self.assertIn("Context Router", skill)
        for command in ("check-update", "plan-update", "apply-update"):
            self.assertNotIn(command, skill)
        self.assertIn("adoption / update / check-update", agents)
        self.assertIn("不自动 check-update", update_doc)
        self.assertIn("只有用户明确批准该计划", update_doc)

    def test_opencode_entries_are_thin(self) -> None:
        skill = (ROOT / ".opencode/skills/themasterplan/SKILL.md").read_text(
            encoding="utf-8"
        )
        command = (ROOT / ".opencode/commands/themasterplan.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Context Router", skill)
        self.assertIn("Load the `themasterplan` skill", command)
        for body in (skill, command):
            self.assertNotIn("api.github", body)
            self.assertNotIn("SemVer", body)
            self.assertNotIn("check-update", body)
            self.assertNotIn("plan-update", body)
            self.assertNotIn("apply-update", body)

    def test_plan_adopt_has_no_adapter_argument(self) -> None:
        from themasterplan import build_parser

        common = [
            "plan-adopt",
            "--source", ".",
            "--profile", "git",
            "--validation-path", "scripts/check.sh",
            "--output", "plan.json",
        ]
        args = build_parser().parse_args(common)
        self.assertFalse(hasattr(args, "adapter"))
        with self.assertRaises(SystemExit):
            build_parser().parse_args(common + ["--adapter", "generic"])

    def test_actions_uses_and_policy_ref_share_target_version(self) -> None:
        body = (ROOT / "docs/client-update-flow.md").read_text(encoding="utf-8")
        self.assertIn("@<target-version>", body)
        self.assertIn("policy-ref: <target-version>", body)
        self.assertIn("必须一致", body)

    def test_legacy_compatibility_surface_preserved(self) -> None:
        tmlib_init = (EXECUTOR_DIR / "tmlib/__init__.py").read_text(encoding="utf-8")
        self.assertIn("TheMasterplanError", tmlib_init)
        self.assertTrue((EXECUTOR_DIR / "themasterplan.py").is_file())
        self.assertTrue((EXECUTOR_DIR / "tmlib/util.py").is_file())
        template = (ROOT / "distribution/templates/agents-managed-block.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("THEMASTERPLAN:BEGIN MANAGED", template)
        workflow = (ROOT / ".github/workflows/themasterplan-check.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("policy-ref", workflow)


if __name__ == "__main__":
    unittest.main()
