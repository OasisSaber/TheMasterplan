"""Temporary-fixture regressions for TMP-CR-01 through TMP-CR-06."""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
EXECUTOR = ROOT / "skills/themasterplan/scripts"
sys.path.insert(0, str(EXECUTOR))

from tmlib.apply import EXECUTOR_FILES, apply_adopt
from tmlib.doctor import doctor
from tmlib.inspect import inspect
from tmlib.planning import plan_adopt
from tmlib.source import resolve_local
from tmlib.update import apply_update, plan_update
from tmlib.update_check import fetch_latest_stable_release, UpdateCheckError
from tmlib.util import TheMasterplanError, safe_join, sha256_of_file, write_json_atomic
from tmlib.verify import verify


class ReviewUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        self.package = Path(self.tmp.name) / "package"
        for part in ("core", "profiles", "distribution", "skills/themasterplan"):
            shutil.copytree(ROOT / part, self.package / part,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.source = resolve_local(self.package, commit="a" * 40)
        self.plan_path = Path(self.tmp.name) / "plan.json"
        plan = plan_adopt(self.root, self.source, profile="git",
                          validation_path="scripts/check.sh")
        write_json_atomic(self.plan_path, plan)
        apply_adopt(self.root, self.plan_path, self.source)
        self.state = json.loads((self.root / ".themasterplan/state.json").read_text())
        (self.root / "README.md").write_bytes(b"private project data\r\n")

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def assert_refused_unchanged(self, plan):
        write_json_atomic(self.plan_path, plan)
        before = self.snapshot()
        with self.assertRaises(TheMasterplanError):
            apply_update(self.root, self.plan_path, self.source)
        self.assertEqual(self.snapshot(), before)

    def test_cr01_forged_unmanaged_delete_is_rejected_without_writes(self):
        plan = plan_update(self.root, self.source, self.state)
        plan["files"].append({"source": None, "destination": "README.md",
                              "ownership": "managed-replace", "required": False,
                              "classification": "REMOVED_UPSTREAM",
                              "observed_sha256": sha256_of_file(self.root / "README.md")})
        self.assert_refused_unchanged(plan)

    def test_cr01_all_executable_fields_are_bound_to_canonical_plan(self):
        base = plan_update(self.root, self.source, self.state)
        for field, value in (("render", True), ("ownership", "generated-if-missing"),
                             ("required", False), ("source", "core/workflow.md")):
            with self.subTest(field=field):
                plan = copy.deepcopy(base)
                op = next(p for p in plan["files"] if p["destination"] == "core/policy.md")
                op[field] = value
                self.assert_refused_unchanged(plan)
        plan = copy.deepcopy(base)
        plan["selection"]["default_branch"] = "different"
        self.assert_refused_unchanged(plan)
        plan = copy.deepcopy(base)
        plan["files"].pop()
        self.assert_refused_unchanged(plan)

    def test_cr01_state_changed_after_plan_is_rejected(self):
        plan = plan_update(self.root, self.source, self.state)
        self.state["adoption"]["date"] = "changed"
        write_json_atomic(self.root / ".themasterplan/state.json", self.state)
        self.assert_refused_unchanged(plan)

    def test_cr02_modified_executor_stops_plan_and_apply(self):
        old_plan = plan_update(self.root, self.source, self.state)
        target = self.root / ".themasterplan/bin/tmlib/source.py"
        target.write_bytes(b"# local executor patch\n")
        plan = plan_update(self.root, self.source, self.state)
        op = next((op for op in plan["files"] if op["destination"] ==
                   ".themasterplan/bin/tmlib/source.py"), None)
        self.assertIsNotNone(op)
        self.assertEqual(op["classification"], "LOCAL_MODIFIED")
        self.assertTrue(plan["stop_conditions"])
        self.assert_refused_unchanged(plan)
        self.assert_refused_unchanged(old_plan)

    def test_cr02_executor_operations_and_actual_writes_are_complete(self):
        target = self.package / "skills/themasterplan/scripts/tmlib/source.py"
        target.write_bytes(target.read_bytes() + b"\n# next version\n")
        plan = plan_update(self.root, self.source, self.state)
        planned = {op["destination"] for op in plan["files"]}
        self.assertTrue({f".themasterplan/bin/{p}" for p in EXECUTOR_FILES} <= planned)
        before = self.snapshot()
        write_json_atomic(self.plan_path, plan)
        result = apply_update(self.root, self.plan_path, self.source)
        after = self.snapshot()
        actual = {p for p, content in after.items() if before.get(p) != content}
        self.assertEqual(actual - {".themasterplan/state.json"}, set(result["written"]))
        self.assertIn(".themasterplan/bin/tmlib/source.py", result["written"])

    def test_cr04_missing_selected_profile_stops_planning_and_apply(self):
        old_plan = plan_update(self.root, self.source, self.state)
        path = self.package / "distribution/manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files"] = [f for f in manifest["files"]
                             if f["destination"] != "profiles/git.md"]
        write_json_atomic(path, manifest)
        before = self.snapshot()
        with self.assertRaises(TheMasterplanError):
            plan_update(self.root, self.source, self.state)
        with self.assertRaises(TheMasterplanError):
            plan_adopt(self.root, self.source, profile="git", validation_path="scripts/check.sh")
        self.assert_refused_unchanged(old_plan)
        self.assertEqual(before, self.snapshot())

    def test_cr04_untracked_missing_profile_is_not_healthy(self):
        del self.state["managed_files"]["profiles/git.md"]
        write_json_atomic(self.root / ".themasterplan/state.json", self.state)
        (self.root / "profiles/git.md").unlink()
        for command in (inspect, verify, doctor):
            with self.subTest(command=command.__name__):
                result = command(self.root)
                self.assertNotIn(result["status"], ("CURRENT", "OK"))
                self.assertTrue(any("profiles/git.md" in s for s in result["issues"]))

    def test_cr04_required_source_disappears_before_adoption_apply(self):
        empty = Path(self.tmp.name) / "new-project"
        empty.mkdir()
        plan = plan_adopt(empty, self.source, profile="git", validation_path="scripts/check.sh")
        write_json_atomic(self.plan_path, plan)
        (self.package / "profiles/git.md").unlink()
        with self.assertRaises(TheMasterplanError):
            apply_adopt(empty, self.plan_path, self.source)
        self.assertEqual(list(empty.iterdir()), [])

    def test_cr04_adoption_plan_cannot_omit_selected_profile(self):
        empty = Path(self.tmp.name) / "new-project"
        empty.mkdir()
        plan = plan_adopt(empty, self.source, profile="git", validation_path="scripts/check.sh")
        plan["files"] = [op for op in plan["files"] if op["destination"] != "profiles/git.md"]
        write_json_atomic(self.plan_path, plan)
        with self.assertRaises(TheMasterplanError):
            apply_adopt(empty, self.plan_path, self.source)
        self.assertEqual(list(empty.iterdir()), [])

    def test_cr05_malformed_nested_state_reports_broken(self):
        for field, value in (("selection", []), ("source", "x"), ("managed_files", []),
                             ("managed_files", {"core/policy.md": []}),
                             ("managed_files", {"core/policy.md": {"ownership": [], "installed_sha256": []}})):
            malformed = copy.deepcopy(self.state)
            malformed[field] = value
            write_json_atomic(self.root / ".themasterplan/state.json", malformed)
            for command in (inspect, verify, doctor):
                with self.subTest(field=field, value=value, command=command.__name__):
                    result = command(self.root)
                    self.assertEqual(result["status"], "BROKEN")
                    self.assertTrue(result["issues"])

    def test_prepared_update_rolls_back_a_late_caught_io_failure(self):
        (self.package / "core/policy.md").write_bytes(b"new policy\n")
        (self.package / "core/workflow.md").write_bytes(b"new workflow\n")
        plan = plan_update(self.root, self.source, self.state)
        write_json_atomic(self.plan_path, plan)
        before = self.snapshot()
        from tmlib import util
        real_write = util.write_bytes_atomic
        count = 0

        def fail_once(path, content):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated write failure")
            return real_write(path, content)

        with mock.patch("tmlib.util.write_bytes_atomic", side_effect=fail_once), \
             self.assertRaisesRegex(TheMasterplanError, "restored"):
            apply_update(self.root, self.plan_path, self.source)
        self.assertEqual(self.snapshot(), before)

    def test_target_mutation_after_preparation_is_rejected_without_overwrite(self):
        (self.package / "core/workflow.md").write_bytes(b"new workflow\n")
        plan = plan_update(self.root, self.source, self.state)
        write_json_atomic(self.plan_path, plan)
        from tmlib import util
        original = util.apply_file_changes

        def intervene(root, changes, expected):
            (root / "README.md").write_bytes(b"unrelated user edit\n")
            (root / "core/workflow.md").write_bytes(b"user edit during preparation\n")
            return original(root, changes, expected)

        with mock.patch("tmlib.update.apply_file_changes", side_effect=intervene), \
             self.assertRaises(TheMasterplanError):
            apply_update(self.root, self.plan_path, self.source)
        self.assertEqual((self.root / "core/workflow.md").read_bytes(), b"user edit during preparation\n")
        self.assertEqual(json.loads((self.root / ".themasterplan/state.json").read_text()), self.state)


class ReviewPathAndStateTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_cr03_windows_junction_component_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real").mkdir()
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "junction"),
                                     str(root / "real")], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with self.assertRaises(TheMasterplanError):
                safe_join(root, "junction/file")

    def test_cr03_final_and_intermediate_internal_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real").mkdir()
            (root / "real/file").write_bytes(b"project-owned")
            try:
                (root / "link").symlink_to(root / "real/file")
                (root / "linked-dir").symlink_to(root / "real", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            for relative in ("link", "linked-dir/file", "linked-dir/new"):
                with self.subTest(relative=relative), self.assertRaises(TheMasterplanError):
                    safe_join(root, relative)
            self.assertEqual(safe_join(root, "real/file"), root / "real/file")

    def test_cr03_windows_ambiguous_relative_paths_rejected(self):
        for relative in ("C:README.md", "file:stream", "core\\policy.md", "", "."):
            with self.subTest(relative=relative), self.assertRaises(TheMasterplanError):
                safe_join(Path.cwd(), relative)

    def test_cr05_invalid_state_cli_returns_broken_json_without_traceback(self):
        samples = ([], None, "x", {}, {"managed_files": []},
                   {"source": [], "selection": "x", "managed_files": {}},
                   {"schema_version": 1, "source": {"version": "v1.0.0"},
                    "selection": {"validation_path": []}, "managed_files": {}})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".themasterplan").mkdir()
            for sample in samples:
                for command in ("inspect", "verify", "doctor"):
                    with self.subTest(sample=sample, command=command):
                        (root / ".themasterplan/state.json").write_text(json.dumps(sample))
                        result = subprocess.run([sys.executable, str(EXECUTOR / "themasterplan.py"),
                                                 command, "--root", str(root)], capture_output=True,
                                                text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                        self.assertNotEqual(result.returncode, 0)
                        self.assertNotIn("Traceback", result.stderr)
                        report = json.loads(result.stdout)
                        self.assertEqual(report["status"], "BROKEN")
                        self.assertTrue(report["issues"])


class ReviewPaginationTests(unittest.TestCase):
    def response(self, releases, link=None):
        result = mock.MagicMock()
        result.__enter__.return_value = result
        result.read.return_value = json.dumps(releases).encode()
        result.headers = {"Link": link} if link else {}
        return result

    def test_cr06_highest_release_on_second_page_is_selected(self):
        next_url = "https://api.github.com/repos/OasisSaber/TheMasterplan/releases?per_page=30&page=2"
        responses = [self.response([{"tag_name": f"v1.0.{n}"} for n in range(30)],
                                   f'<{next_url}>; rel="next"'),
                     self.response([{"tag_name": "v9.0.0"}, {"tag_name": "v2.0.0"}])]
        with mock.patch("urllib.request.urlopen", side_effect=responses) as fetch, \
             mock.patch("tmlib.update_check._resolve_tag_commit", return_value="b" * 40):
            result = fetch_latest_stable_release("OasisSaber/TheMasterplan")
        self.assertEqual(result.version, "v9.0.0")
        self.assertEqual(fetch.call_count, 2)

    def test_cr06_incomplete_or_unsafe_pagination_fails_closed(self):
        for link in ('<https://evil.invalid/releases>; rel="next"',
                     '<https://api.github.com/repos/Other/Repo/releases?page=2>; rel="next"',
                     'not a link; rel="next"',
                     '<https://api.github.com/repos/OasisSaber/TheMasterplan/releases?per_page=30&page=999>; rel="next"',
                     '<https://api.github.com/repos/OasisSaber/TheMasterplan/releases?per_page=30>; rel="next"'):
            with self.subTest(link=link), \
                 mock.patch("urllib.request.urlopen", return_value=self.response([{"tag_name": "v1.0.0"}], link)), \
                 mock.patch("tmlib.update_check._resolve_tag_commit", return_value="b" * 40), \
                 self.assertRaises(UpdateCheckError):
                fetch_latest_stable_release("OasisSaber/TheMasterplan")

    def test_cr06_page_limit_does_not_claim_latest(self):
        next_url = "https://api.github.com/repos/OasisSaber/TheMasterplan/releases?per_page=30&page=2"
        with mock.patch("tmlib.update_check.MAX_RELEASE_PAGES", 1), \
             mock.patch("urllib.request.urlopen", return_value=self.response(
                 [{"tag_name": "v1.0.0"}], f'<{next_url}>; rel="next"')), \
             self.assertRaisesRegex(UpdateCheckError, "limit"):
            fetch_latest_stable_release("OasisSaber/TheMasterplan")

    def test_cr06_old_single_page_cache_is_not_trusted(self):
        from tmlib.update_check import _read_cache
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json_atomic(root / ".themasterplan/cache/update-check.json", {
                "checked_at": __import__("time").time(),
                "repository": "OasisSaber/TheMasterplan", "include_prerelease": False,
                "latest": {"version": "v9.0.0", "commit": "a" * 40}})
            self.assertIsNone(_read_cache(root, "OasisSaber/TheMasterplan", include_prerelease=False))


if __name__ == "__main__":
    unittest.main()
