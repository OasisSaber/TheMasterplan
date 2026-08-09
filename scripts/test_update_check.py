"""Tests for the v3.1.1 read-only update detection (check-update).

Covers the 20-item plan: status machine, draft/prerelease filtering, SemVer
parsing, tag-to-SHA resolution, network failure, rate limit, corrupted state,
zero-write guarantees, Skill user gates, OpenCode thin-loader discipline,
plan-adopt adapter choice, Actions consistency, and v3 compatibility surface.
"""

from __future__ import annotations

import http.server
import json
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = ROOT / "skills" / "themasterplan" / "scripts"

sys.path.insert(0, str(EXECUTOR_DIR))
from awlib.update_check import (  # noqa: E402
    UpdateCheckError,
    check_update,
    fetch_latest_stable_release,
    read_current_identity,
)

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CURRENT_SHA = "a" * 40
NEXT_SHA = "b" * 40
PRE_SHA = "c" * 40
STABLE_RELEASE = {
    "tag_name": "v3.1.1",
    "html_url": "https://example.com/releases/v3.1.1",
    "published_at": "2026-08-04T00:00:00Z",
    "prerelease": False,
    "draft": False,
}
PRE_RELEASE = {
    "tag_name": "v3.2.0",
    "html_url": "https://example.com/releases/v3.2.0",
    "published_at": "2026-08-04T01:00:00Z",
    "prerelease": True,
    "draft": False,
}
DRAFT_RELEASE = {
    "tag_name": "v3.9.9",
    "html_url": "https://example.com/releases/v3.9.9",
    "published_at": "2026-08-04T02:00:00Z",
    "prerelease": False,
    "draft": True,
}
NON_SEMVER_RELEASE = {
    "tag_name": "latest",
    "html_url": "https://example.com/releases/latest",
    "published_at": "2026-08-04T03:00:00Z",
    "prerelease": False,
    "draft": False,
}

RELEASES_PAYLOAD = [
    NON_SEMVER_RELEASE,
    DRAFT_RELEASE,
    PRE_RELEASE,
    STABLE_RELEASE,
]

STATE_JSON = {
    "schema_version": 1,
    "source": {
        "repository": "OasisSaber/TheMasterplan",
        "version": "v3.1.0",
        "commit": CURRENT_SHA,
    },
}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102
        pass


class UpdateCheckHttpTests(unittest.TestCase):
    """Network tests against a local HTTP server (no live GitHub)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="aw-update-check-"))
        handler = lambda *args, **kwargs: QuietHandler(  # noqa: E731
            *args, directory=str(cls.tmp), **kwargs
        )
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(
            target=cls.httpd.serve_forever, daemon=True
        )
        cls.thread.start()
        cls._releases_path = cls.tmp / "releases.json"
        cls._releases_path.write_text(
            json.dumps(RELEASES_PAYLOAD), encoding="utf-8"
        )
        (cls.tmp / "commit-v3.1.1.json").write_text(
            json.dumps({"sha": NEXT_SHA}), encoding="utf-8"
        )
        (cls.tmp / "commit-v3.2.0.json").write_text(
            json.dumps({"sha": PRE_SHA}), encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _set_releases(self, payload: list[dict]) -> None:
        self._releases_path.write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def _patch_urls(self) -> None:
        import awlib.source as source_mod
        import awlib.update_check as check_mod

        check_mod.RELEASES_URL = (
            f"http://127.0.0.1:{self.port}/releases.json"
        )
        source_mod.API_COMMIT_URL = (
            f"http://127.0.0.1:{self.port}/commit-{{ref}}.json"
        )
        self._source_mod = source_mod
        self._check_mod = check_mod

    def _unpatch_urls(self) -> None:
        import awlib.source as source_mod
        import awlib.update_check as check_mod

        source_mod.API_COMMIT_URL = (
            "https://api.github.com/repos/{repository}/commits/{ref}"
        )
        check_mod.RELEASES_URL = (
            "https://api.github.com/repos/{repository}/releases?per_page=30"
        )

    def test_release_tag_resolves_to_full_sha(self) -> None:
        self._patch_urls()
        try:
            release = fetch_latest_stable_release("OasisSaber/TheMasterplan")
        finally:
            self._unpatch_urls()
        self.assertEqual(release.version, "v3.1.1")
        self.assertEqual(release.commit, NEXT_SHA)
        self.assertRegex(release.commit, FULL_SHA_RE)

    def test_draft_is_ignored(self) -> None:
        self._patch_urls()
        try:
            release = fetch_latest_stable_release("OasisSaber/TheMasterplan")
        finally:
            self._unpatch_urls()
        self.assertEqual(release.version, "v3.1.1")

    def test_prerelease_ignored_by_default(self) -> None:
        self._patch_urls()
        try:
            release = fetch_latest_stable_release("OasisSaber/TheMasterplan")
        finally:
            self._unpatch_urls()
        self.assertEqual(release.version, "v3.1.1")

    def test_include_prerelease_picks_highest(self) -> None:
        self._patch_urls()
        try:
            release = fetch_latest_stable_release(
                "OasisSaber/TheMasterplan", include_prerelease=True
            )
        finally:
            self._unpatch_urls()
        self.assertEqual(release.version, "v3.2.0")
        self.assertEqual(release.commit, PRE_SHA)

    def test_non_semver_tag_ignored(self) -> None:
        self._set_releases([NON_SEMVER_RELEASE, STABLE_RELEASE])
        self._patch_urls()
        try:
            release = fetch_latest_stable_release("OasisSaber/TheMasterplan")
        finally:
            self._unpatch_urls()
        self.assertEqual(release.version, "v3.1.1")

    def _check(
        self,
        version: str,
        *,
        commit: str = CURRENT_SHA,
    ) -> dict:
        self._patch_urls()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".aw").mkdir(parents=True)
                state = dict(STATE_JSON)
                state["source"] = dict(
                    state["source"],
                    version=version,
                    commit=commit,
                )
                (root / ".aw/state.json").write_text(
                    json.dumps(state), encoding="utf-8"
                )
                return check_update(root, use_cache=False)
        finally:
            self._unpatch_urls()

    def test_status_update_available(self) -> None:
        result = self._check("v3.1.0")
        self.assertEqual(result["status"], "UPDATE_AVAILABLE")
        self.assertEqual(result["latest"]["version"], "v3.1.1")
        self.assertEqual(result["latest"]["commit"], NEXT_SHA)
        self.assertEqual(result["recommended_next_step"], "ask-user")
        self.assertFalse(result["writes_performed"])

    def test_status_current(self) -> None:
        result = self._check("v3.1.1", commit=NEXT_SHA)
        self.assertEqual(result["status"], "CURRENT")
        self.assertEqual(result["recommended_next_step"], "continue")

    def test_same_version_different_commit_is_unknown(self) -> None:
        result = self._check("v3.1.1", commit=CURRENT_SHA)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["recommended_next_step"], "continue")

    def test_status_ahead(self) -> None:
        result = self._check("v3.2.0")
        self.assertEqual(result["status"], "AHEAD")
        self.assertEqual(result["recommended_next_step"], "continue")

    def test_state_file_untouched_when_update_available(self) -> None:
        self._patch_urls()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".aw").mkdir(parents=True)
                state = dict(STATE_JSON)
                state["source"] = dict(state["source"], version="v3.1.0")
                state_path = root / ".aw/state.json"
                state_path.write_text(json.dumps(state), encoding="utf-8")
                before = state_path.read_bytes()
                check_update(root, use_cache=False)
                after = state_path.read_bytes()
        finally:
            self._unpatch_urls()
        self.assertEqual(before, after)

    def test_tag_resolve_failure_is_unavailable(self) -> None:
        self._set_releases(
            [
                {
                    "tag_name": "v9.9.9",
                    "html_url": "https://example.com/releases/v9.9.9",
                    "published_at": "2026-08-04T04:00:00Z",
                    "prerelease": False,
                    "draft": False,
                }
            ]
        )
        self._patch_urls()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".aw").mkdir(parents=True)
                (root / ".aw/state.json").write_text(
                    json.dumps(STATE_JSON), encoding="utf-8"
                )
                result = check_update(root, use_cache=False)
        finally:
            self._unpatch_urls()
            self._set_releases(RELEASES_PAYLOAD)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIn("cannot resolve tag", result["reason"])


class RateLimitHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(403)
        self.end_headers()
        self.wfile.write(b'{"message": "rate limit exceeded"}')

    def log_message(self, *args):  # noqa: D102
        pass


class UpdateCheckOfflineTests(unittest.TestCase):
    """No-network and failure-path tests."""

    def test_network_failure_is_unavailable(self) -> None:
        import awlib.update_check as check_mod

        original = check_mod.RELEASES_URL
        check_mod.RELEASES_URL = "http://127.0.0.1:1/releases.json"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".aw").mkdir(parents=True)
                (root / ".aw/state.json").write_text(
                    json.dumps(STATE_JSON), encoding="utf-8"
                )
                result = check_update(root, use_cache=False)
        finally:
            check_mod.RELEASES_URL = original
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["latest"])
        self.assertIn("release query failed", result["reason"])
        self.assertFalse(result["writes_performed"])

    def test_rate_limit_is_unavailable(self) -> None:
        import awlib.update_check as check_mod

        httpd = socketserver.TCPServer(("127.0.0.1", 0), RateLimitHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        original = check_mod.RELEASES_URL
        check_mod.RELEASES_URL = f"http://127.0.0.1:{port}/releases.json"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".aw").mkdir(parents=True)
                (root / ".aw/state.json").write_text(
                    json.dumps(STATE_JSON), encoding="utf-8"
                )
                result = check_update(root, use_cache=False)
        finally:
            check_mod.RELEASES_URL = original
            httpd.shutdown()
            httpd.server_close()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIn("rate limit", result["reason"])

    def test_no_state_file_is_not_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = check_update(Path(tmp), use_cache=False)
        self.assertEqual(result["status"], "NOT_ADOPTED")
        self.assertFalse(result["writes_performed"])

    def test_corrupted_state_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".aw").mkdir(parents=True)
            (root / ".aw/state.json").write_text(
                "{not json", encoding="utf-8"
            )
            with self.assertRaises(UpdateCheckError):
                check_update(root)

    def test_corrupted_state_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".aw").mkdir(parents=True)
            (root / ".aw/state.json").write_text(
                "{not json", encoding="utf-8"
            )
            proc = subprocess.run(
                [sys.executable, str(EXECUTOR_DIR / "aw.py"),
                 "check-update", "--root", str(root)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 1)


class UpdateCheckStateTests(unittest.TestCase):
    """Status machine and zero-write guarantees."""

    def _adopt(self, root: Path, version: str = "v3.1.0") -> Path:
        (root / ".aw").mkdir(parents=True)
        state = dict(STATE_JSON)
        state["source"] = dict(state["source"], version=version)
        (root / ".aw/state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        return root / ".aw/state.json"

    def test_check_update_does_not_modify_state(self) -> None:
        import awlib.update_check as check_mod

        original = check_mod.RELEASES_URL
        check_mod.RELEASES_URL = "http://127.0.0.1:1/releases.json"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = self._adopt(root, "v3.1.0")
                before = state_path.read_bytes()
                check_update(root, use_cache=True)
                after = state_path.read_bytes()
        finally:
            check_mod.RELEASES_URL = original
        self.assertEqual(before, after)

    def test_check_update_does_not_modify_managed_files(self) -> None:
        import awlib.update_check as check_mod

        original = check_mod.RELEASES_URL
        check_mod.RELEASES_URL = "http://127.0.0.1:1/releases.json"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._adopt(root, "v3.1.0")
                managed = {
                    "AGENTS.md": b"# project",
                    "core/policy.md": b"policy",
                    "core/workflow.md": b"workflow",
                    "scripts/check.sh": b"#!/bin/bash\n",
                }
                for relative, content in managed.items():
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                before = {
                    relative: (root / relative).read_bytes()
                    for relative in managed
                }
                result = check_update(root, use_cache=True)
                after = {
                    relative: (root / relative).read_bytes()
                    for relative in managed
                }
        finally:
            check_mod.RELEASES_URL = original
        self.assertEqual(before, after)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertFalse(result["writes_performed"])


class UpdateCheckContractTests(unittest.TestCase):
    """Static contract checks: Skill gates, thin loaders, compatibility."""

    def test_skill_has_user_choice_gate(self) -> None:
        body = (ROOT / "skills/themasterplan/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("更新检测", body)
        self.assertIn("由用户选择", body)
        self.assertIn("plan-update", body)

    def test_skill_has_no_automatic_apply(self) -> None:
        body = (ROOT / "skills/themasterplan/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("不得运行 `apply-update`", body)
        self.assertNotIn("自动执行 apply-update", body)

    def test_opencode_entries_do_not_copy_remote_logic(self) -> None:
        for path in (
            ROOT / ".opencode/skills/themasterplan/SKILL.md",
            ROOT / ".opencode/commands/themasterplan.md",
        ):
            body = path.read_text(encoding="utf-8")
            self.assertNotIn("api.github", body)
            self.assertNotIn("SemVer", body)
            self.assertTrue(
                "更新检测" in body or "update detection" in body,
                f"{path} must reference the update detection step",
            )

    def test_plan_adopt_accepts_agent_orchestrator(self) -> None:
        from aw import build_parser

        args = build_parser().parse_args(
            [
                "plan-adopt",
                "--source",
                ".",
                "--profile",
                "git",
                "--adapter",
                "agent-orchestrator",
                "--validation-path",
                "scripts/check.sh",
                "--output",
                "plan.json",
            ]
        )
        self.assertEqual(args.adapter, "agent-orchestrator")

    def test_actions_uses_and_policy_ref_update_together(self) -> None:
        body = (ROOT / "docs/client-update-flow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("uses", body)
        self.assertIn("policy-ref", body)
        self.assertIn("同时更新", body)

    def test_legacy_compatibility_surface_preserved(self) -> None:
        awlib_init = (EXECUTOR_DIR / "awlib/__init__.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("AwError", awlib_init)
        self.assertTrue((EXECUTOR_DIR / "aw.py").is_file())
        self.assertTrue((EXECUTOR_DIR / "awlib/util.py").is_file())
        template = (
            ROOT / "distribution/templates/agents-managed-block.md"
        ).read_text(encoding="utf-8")
        self.assertIn("AW:BEGIN MANAGED", template)
        workflow = (ROOT / ".github/workflows/aw-check.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("policy-ref", workflow)


class UpdateCheckCacheTests(unittest.TestCase):
    """Cache keying, TTL and corruption robustness."""

    def _root(self) -> Path:
        tmp = tempfile.mkdtemp(prefix="aw-cache-test-")
        root = Path(tmp)
        (root / ".aw").mkdir(parents=True)
        (root / ".aw/state.json").write_text(
            json.dumps(STATE_JSON), encoding="utf-8"
        )
        return root

    def test_cache_is_keyed_by_prerelease_flag(self) -> None:
        import awlib.update_check as check_mod

        root = self._root()
        latest = {"version": "v3.2.0", "commit": PRE_SHA}
        check_mod._write_cache(
            root, "OasisSaber/TheMasterplan", latest,
            include_prerelease=True,
        )
        default_read = check_mod._read_cache(
            root, "OasisSaber/TheMasterplan", include_prerelease=False
        )
        prerelease_read = check_mod._read_cache(
            root, "OasisSaber/TheMasterplan", include_prerelease=True
        )
        self.assertIsNone(default_read)
        self.assertEqual(prerelease_read, latest)

    def test_expired_cache_is_ignored(self) -> None:
        import awlib.update_check as check_mod

        root = self._root()
        cache_path = root / ".aw/cache/update-check.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "checked_at": 0.0,
                    "repository": "OasisSaber/TheMasterplan",
                    "include_prerelease": False,
                    "latest": {"version": "v3.1.1", "commit": NEXT_SHA},
                }
            ),
            encoding="utf-8",
        )
        cached = check_mod._read_cache(
            root, "OasisSaber/TheMasterplan", include_prerelease=False
        )
        self.assertIsNone(cached)

    def test_corrupted_cache_is_ignored(self) -> None:
        import awlib.update_check as check_mod

        root = self._root()
        cache_path = root / ".aw/cache/update-check.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("{not json", encoding="utf-8")
        cached = check_mod._read_cache(
            root, "OasisSaber/TheMasterplan", include_prerelease=False
        )
        self.assertIsNone(cached)


class UpdateCheckCliTests(unittest.TestCase):
    """CLI exit codes 2 and 3."""

    def test_invalid_repository_exits_2(self) -> None:
        import argparse

        from aw import _cmd_check_update

        args = argparse.Namespace(
            root=".", repository="not-a-repo", include_prerelease=False,
            no_cache=False,
        )
        self.assertEqual(_cmd_check_update(args), 2)

    def test_unavailable_exits_3(self) -> None:
        import argparse
        from unittest import mock

        from aw import _cmd_check_update

        args = argparse.Namespace(
            root=".", repository=None, include_prerelease=False,
            no_cache=False,
        )
        result = {
            "schema_version": 1,
            "status": "UNAVAILABLE",
            "current": None,
            "latest": None,
            "reason": "offline",
            "recommended_next_step": "continue-current-version",
            "writes_performed": False,
        }
        with mock.patch("aw.check_update", return_value=result):
            self.assertEqual(_cmd_check_update(args), 3)


if __name__ == "__main__":
    unittest.main()
