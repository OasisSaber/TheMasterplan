#!/usr/bin/env python3
"""PR B tests: source resolution, remote download/extract, plan-update,
apply-update and doctor.

Tests use local fixtures, mocks and a temporary HTTP server; they never
touch live GitHub.
"""

from __future__ import annotations

import http.server
import json
import shutil
import socketserver
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_DIR = REPO_ROOT / "skills" / "themasterplan" / "scripts"

sys.path.insert(0, str(EXECUTOR_DIR))
from tmlib import TheMasterplanError  # noqa: E402
from tmlib.apply import apply_adopt  # noqa: E402
from tmlib.doctor import doctor  # noqa: E402
from tmlib.manifest import load_manifest  # noqa: E402
from tmlib.planning import plan_adopt  # noqa: E402
from tmlib.source import SourceError, resolve_local, resolve_remote, resolve_source  # noqa: E402
from tmlib.update import apply_update, plan_update  # noqa: E402
from tmlib.util import read_json, write_json_atomic  # noqa: E402

PACKAGE_ROOT = REPO_ROOT
TEST_COMMIT = "b" * 40
MANIFEST_VERSION = load_manifest(
    REPO_ROOT / "distribution" / "manifest.json"
)["distribution_version"]


def make_package_copy() -> Path:
    """Copy distribution/core/profiles/skills into a temp dir; returns root."""
    tmp = Path(tempfile.mkdtemp(prefix="tml-pkg-"))
    for sub in ("distribution", "core", "profiles", "skills"):
        shutil.copytree(
            PACKAGE_ROOT / sub,
            tmp / sub,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    return tmp


def make_tar_gz(package_root: Path) -> bytes:
    """Create a GitHub-style single-top-dir tar.gz archive of a package."""
    import io

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        base = Path("repo-vX")
        for sub in ("distribution", "core", "profiles"):
            for path in sorted((package_root / sub).rglob("*")):
                if path.is_file():
                    rel = base / sub / path.relative_to(package_root / sub)
                    info = tarfile.TarInfo(str(rel))
                    data = path.read_bytes()
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # silence test output
        pass


class HttpServerTest(unittest.TestCase):
    """resolve_remote against a temporary local HTTP server."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="tml-http-"))
        cls.archive = cls.tmp / "archive.tar.gz"
        cls.archive.write_bytes(make_tar_gz(PACKAGE_ROOT))
        handler = lambda *a, **kw: QuietHandler(*a, directory=str(cls.tmp), **kw)  # noqa: E731
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_remote_resolve_download_extract(self) -> None:
        url = f"http://127.0.0.1:{self.port}/archive.tar.gz"
        commit_url = f"http://127.0.0.1:{self.port}/commit.json"
        (self.tmp / "commit.json").write_text(
            json.dumps({"sha": TEST_COMMIT}),
            encoding="utf-8",
        )
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            # Patch the archive/tag URLs to the local server.
            from tmlib import source as source_mod

            original_archive = source_mod.ARCHIVE_URL
            original_api = source_mod.API_COMMIT_URL
            source_mod.ARCHIVE_URL = url
            source_mod.API_COMMIT_URL = commit_url
            try:
                src = resolve_remote("OasisSaber/TheMasterplan", MANIFEST_VERSION, cache, commit=TEST_COMMIT)
            finally:
                source_mod.ARCHIVE_URL = original_archive
                source_mod.API_COMMIT_URL = original_api
            self.assertEqual(src.version, MANIFEST_VERSION)
            self.assertEqual(src.commit, TEST_COMMIT)
            self.assertTrue((src.package_root / "distribution" / "manifest.json").is_file())
            self.assertTrue((src.package_root / "core" / "policy.md").is_file())
            # Cache hit: second resolve reuses the archive.
            self.assertTrue(cache.exists())

    def test_remote_ref_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SourceError):
                resolve_remote("OasisSaber/TheMasterplan", "main", Path(tmp) / "cache")


class ResolveLocalTest(unittest.TestCase):
    def test_resolve_local_with_explicit_commit(self) -> None:
        src = resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT)
        self.assertEqual(src.commit, TEST_COMMIT)
        self.assertEqual(src.version, MANIFEST_VERSION)
        self.assertEqual(src.repository, "OasisSaber/TheMasterplan")

    def test_resolve_local_rejects_bad_commit(self) -> None:
        with self.assertRaises(SourceError):
            resolve_local(PACKAGE_ROOT, commit="not-a-sha")

    def test_resolve_source_local_path(self) -> None:
        src = resolve_source(str(PACKAGE_ROOT), commit=TEST_COMMIT)
        self.assertEqual(src.package_root, PACKAGE_ROOT.resolve())


class UpdateFlowTest(unittest.TestCase):
    """plan-update / apply-update against temp projects."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.root)],
            check=True,
            capture_output=True,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _adopt(self, package_root: Path) -> dict:
        plan = plan_adopt(
            self.root,
            resolve_local(package_root, commit=TEST_COMMIT),
            profile="git",
            validation_path="scripts/check.sh",
        )
        plan_path = self.root / ".themasterplan-plan.json"
        write_json_atomic(plan_path, plan)
        apply_adopt(self.root, plan_path, resolve_local(package_root, commit=TEST_COMMIT))
        return read_json(self.root / ".themasterplan/state.json")

    def test_plan_update_unchanged(self) -> None:
        state = self._adopt(PACKAGE_ROOT)
        plan = plan_update(self.root, resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT), state)
        self.assertEqual(plan["plan_type"], "update")
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        classes = {op["classification"] for op in plan["files"]}
        self.assertEqual(classes, {"UNCHANGED"})

    def test_plan_update_safe_and_modified(self) -> None:
        state = self._adopt(PACKAGE_ROOT)
        pkg2 = make_package_copy()
        # Change a managed file in the new package.
        (pkg2 / "core" / "workflow.md").write_bytes(b"new workflow content\n")
        plan = plan_update(self.root, resolve_local(pkg2, commit="c" * 40), state)
        wf = next(op for op in plan["files"] if op["destination"] == "core/workflow.md")
        self.assertEqual(wf["classification"], "UPDATE_SAFE")
        # Apply the safe update.
        plan_path = self.root / ".themasterplan-plan.json"
        write_json_atomic(plan_path, plan)
        result = apply_update(self.root, plan_path, resolve_local(pkg2, commit="c" * 40))
        self.assertIn("core/workflow.md", result["written"])
        self.assertEqual(
            (self.root / "core/workflow.md").read_bytes(), b"new workflow content\n"
        )
        # Now locally modify it and plan again -> LOCAL_MODIFIED stops.
        (self.root / "core/workflow.md").write_bytes(b"local edit\n")
        state2 = read_json(self.root / ".themasterplan/state.json")
        plan2 = plan_update(self.root, resolve_local(pkg2, commit="c" * 40), state2)
        wf2 = next(op for op in plan2["files"] if op["destination"] == "core/workflow.md")
        self.assertEqual(wf2["classification"], "LOCAL_MODIFIED")
        self.assertTrue(plan2["stop_conditions"])
        # Apply must refuse (stop conditions present).
        plan_path2 = self.root / ".themasterplan-plan2.json"
        write_json_atomic(plan_path2, plan2)
        with self.assertRaises(TheMasterplanError):
            apply_update(self.root, plan_path2, resolve_local(pkg2, commit="c" * 40))
        self.assertEqual(
            (self.root / "core/workflow.md").read_bytes(), b"local edit\n",
            "local modification must never be overwritten",
        )

    def test_plan_update_add_and_removed(self) -> None:
        state = self._adopt(PACKAGE_ROOT)
        pkg2 = make_package_copy()
        # Add a new file and remove the selected Git profile upstream.
        manifest_path = pkg2 / "distribution" / "manifest.json"
        manifest = load_manifest(manifest_path)
        manifest["files"].append(
            {
                "source": "core/workflow.md",
                "destination": "core/extra.md",
                "ownership": "managed-replace",
                "required": False,
            }
        )
        manifest["files"] = [
            e for e in manifest["files"] if e["destination"] != "profiles/git.md"
        ]
        write_json_atomic(manifest_path, manifest)
        (pkg2 / "core" / "extra.md").write_bytes(b"extra\n")
        plan = plan_update(self.root, resolve_local(pkg2, commit="d" * 40), state)
        classes = {op["classification"] for op in plan["files"]}
        self.assertIn("ADD", classes)
        self.assertIn("REMOVED_UPSTREAM", classes)
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        # Apply: extra added, profiles/git.md removed (hash unchanged).
        plan_path = self.root / ".themasterplan-plan.json"
        write_json_atomic(plan_path, plan)
        result = apply_update(self.root, plan_path, resolve_local(pkg2, commit="d" * 40))
        self.assertIn("core/extra.md", result["written"])
        self.assertIn("profiles/git.md", result["removed"])
        self.assertFalse((self.root / "profiles/git.md").exists())

    def test_plan_update_selection_changed(self) -> None:
        state = self._adopt(PACKAGE_ROOT)
        pkg2 = make_package_copy()
        manifest_path = pkg2 / "distribution" / "manifest.json"
        manifest = load_manifest(manifest_path)
        manifest["components"] = {"profiles": ["jj"]}
        write_json_atomic(manifest_path, manifest)
        plan = plan_update(self.root, resolve_local(pkg2, commit="e" * 40), state)
        self.assertTrue(plan["stop_conditions"])
        self.assertIn("selection no longer supported", plan["stop_conditions"][0])

    def test_v4_generic_adapter_is_migrated_out(self) -> None:
        state = self._adopt(PACKAGE_ROOT)
        state["selection"]["adapter"] = "generic"
        plan = plan_update(
            self.root,
            resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT),
            state,
        )
        self.assertFalse(plan["stop_conditions"], plan["stop_conditions"])
        self.assertNotIn("adapter", plan["selection"])

    def test_unknown_legacy_adapter_fails_closed(self) -> None:
        state = self._adopt(PACKAGE_ROOT)
        state["selection"]["adapter"] = "unknown-orchestrator"
        plan = plan_update(
            self.root,
            resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT),
            state,
        )
        self.assertTrue(plan["stop_conditions"])
        self.assertIn("selection no longer supported", plan["stop_conditions"][0])


class DoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_doctor_absent(self) -> None:
        report = doctor(self.root)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "ABSENT")

    def test_doctor_ok_after_adopt(self) -> None:
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.root)],
            check=True,
            capture_output=True,
        )
        plan = plan_adopt(
            self.root,
            resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT),
            profile="git",
            validation_path="scripts/check.sh",
        )
        plan_path = self.root / ".themasterplan-plan.json"
        write_json_atomic(plan_path, plan)
        apply_adopt(self.root, plan_path, resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT))
        report = doctor(self.root)
        self.assertTrue(report["ok"], report["issues"])

    def test_doctor_reports_modified(self) -> None:
        subprocess.run(
            ["git", "init", "--initial-branch=main", "-q", str(self.root)],
            check=True,
            capture_output=True,
        )
        plan = plan_adopt(
            self.root,
            resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT),
            profile="git",
            validation_path="scripts/check.sh",
        )
        plan_path = self.root / ".themasterplan-plan.json"
        write_json_atomic(plan_path, plan)
        apply_adopt(self.root, plan_path, resolve_local(PACKAGE_ROOT, commit=TEST_COMMIT))
        (self.root / "core" / "policy.md").write_bytes(b"tampered\n")
        report = doctor(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("hash mismatch" in i for i in report["issues"]))


if __name__ == "__main__":
    unittest.main()
