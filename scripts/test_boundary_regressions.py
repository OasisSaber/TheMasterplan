"""Temporary-fixture regressions for the post-PR98 boundary review."""

import copy
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_review_regressions as fixtures
from tmlib import util
from tmlib.doctor import doctor
from tmlib.inspect import inspect
from tmlib.manifest import validate_files
from tmlib.update import apply_update, plan_update
from tmlib.verify import verify


class BoundaryUpdateTests(unittest.TestCase):
    setUp = fixtures.ReviewUpdateTests.setUp
    snapshot = fixtures.ReviewUpdateTests.snapshot

    def test_required_installed_closure_is_not_implicitly_repaired(self):
        original = copy.deepcopy(self.state)
        for relative in ("core/workflow.md", "core/policy.md", "profiles/git.md"):
            for damage in ("record", "file", "both", "ownership", "hash"):
                with self.subTest(relative=relative, damage=damage):
                    self.state = copy.deepcopy(original)
                    target = self.root / relative
                    data = target.read_bytes()
                    old_plan = plan_update(self.root, self.source, self.state)
                    if damage in ("record", "both"):
                        del self.state["managed_files"][relative]
                    if damage in ("file", "both"):
                        target.unlink()
                    if damage == "ownership":
                        self.state["managed_files"][relative]["ownership"] = "managed-block"
                    if damage == "hash":
                        self.state["managed_files"][relative]["installed_sha256"] = "0" * 64
                    util.write_json_atomic(self.root / ".themasterplan/state.json", self.state)
                    before = self.snapshot()
                    try:
                        plan = plan_update(self.root, self.source, self.state)
                    except util.TheMasterplanError:
                        pass
                    else:
                        self.assertTrue(plan["stop_conditions"], "broken closure must stop update")
                    util.write_json_atomic(self.plan_path, old_plan)
                    with self.assertRaises(util.TheMasterplanError):
                        apply_update(self.root, self.plan_path, self.source)
                    self.assertEqual(self.snapshot(), before)
                    target.write_bytes(data)
        self.state = original

    def test_diagnostics_and_update_are_independent_of_foreign_cwd(self):
        plan = plan_update(self.root, self.source, self.state)
        util.write_json_atomic(self.plan_path, plan)
        foreign = Path(self.tmp.name) / "foreign"
        foreign.mkdir()
        try:
            (foreign / "core").symlink_to(self.root / "core", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        previous = Path.cwd()
        baseline = {command.__name__: command(self.root)["status"]
                    for command in (inspect, verify, doctor)}
        try:
            os.chdir(foreign)
            util.validate_state(self.state)
            for command in (inspect, verify, doctor):
                self.assertEqual(command(self.root)["status"], baseline[command.__name__])
            self.assertEqual(plan_update(self.root, self.source, self.state), plan)
            apply_update(self.root, self.plan_path, self.source)
        finally:
            os.chdir(previous)

    def test_case_alias_state_and_manifest_are_rejected_before_writes(self):
        self.state["managed_files"]["Core/policy.md"] = copy.deepcopy(
            self.state["managed_files"]["core/policy.md"])
        with self.assertRaises(util.TheMasterplanError):
            util.validate_state(self.state)
        with self.assertRaises(util.TheMasterplanError):
            plan_update(self.root, self.source, self.state)
        entries = [{"source": "core/policy.md", "destination": dest,
                    "ownership": "managed-replace"}
                   for dest in ("core/policy.md", "Core/other.md")]
        with self.assertRaises(util.TheMasterplanError):
            validate_files(entries)

    def test_target_collection_collision_is_rejected_even_for_missing_files(self):
        with self.assertRaises(util.TheMasterplanError):
            util.apply_file_changes(self.root, {"new/File": b"one", "new/file": b"two"},
                                    {"new/File": None, "new/file": None})
        self.assertFalse((self.root / "new").exists())

    def test_case_alias_plan_is_refused_without_writes(self):
        plan = plan_update(self.root, self.source, self.state)
        forged = copy.deepcopy(next(op for op in plan["files"]
                                   if op["destination"] == "core/policy.md"))
        forged["destination"] = "Core/policy.md"
        plan["files"].append(forged)
        util.write_json_atomic(self.plan_path, plan)
        before = self.snapshot()
        with self.assertRaises(util.TheMasterplanError):
            apply_update(self.root, self.plan_path, self.source)
        self.assertEqual(self.snapshot(), before)

    def test_required_local_change_matching_new_package_still_stops(self):
        for root in (self.root, self.package):
            (root / "core/policy.md").write_bytes(b"local change equals upstream\n")
        plan = plan_update(self.root, self.source, self.state)
        operation = next(op for op in plan["files"] if op["destination"] == "core/policy.md")
        self.assertEqual(operation["classification"], "LOCAL_MODIFIED")
        self.assertTrue(plan["stop_conditions"])
        util.write_json_atomic(self.plan_path, plan)
        before = self.snapshot()
        with self.assertRaises(util.TheMasterplanError):
            apply_update(self.root, self.plan_path, self.source)
        self.assertEqual(self.snapshot(), before)

    @unittest.skipIf(os.name == "nt", "POSIX permission-bit semantics")
    def test_update_preserves_executable_mode_and_rollback(self):
        target = self.root / "core/policy.md"
        target.chmod(0o755)
        (self.package / "core/policy.md").write_bytes(b"new policy\n")
        (self.package / "core/workflow.md").write_bytes(b"new workflow\n")
        plan = plan_update(self.root, self.source, self.state)
        util.write_json_atomic(self.plan_path, plan)
        before = self.snapshot()
        real_write = util.write_bytes_atomic
        calls = 0
        def fail_once(path, content, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("late update failure")
            return real_write(path, content, **kwargs)
        with mock.patch("tmlib.util.write_bytes_atomic", side_effect=fail_once), \
             self.assertRaises(util.TheMasterplanError):
            apply_update(self.root, self.plan_path, self.source)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)
        apply_update(self.root, self.plan_path, self.source)
        self.assertEqual(target.read_bytes(), b"new policy\n")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)


class BoundaryPathTests(unittest.TestCase):
    def test_windows_noncanonical_names_are_rejected_on_every_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            for relative in ("core/policy.md.", "core/policy.md ", "core./policy.md",
                             "NUL.txt", "nested/CON", "COM1", "lpt9.log", "aux.tar.gz",
                             "CONIN$", "conout$.txt", "NUL .txt", "COM1 .log",
                             "COM¹.txt", "LPT²", "PRN", "a?b", "a*b", 'a"b',
                             "a<b", "a>b", "a|b", "a\x01b", "a\x1fb"):
                with self.subTest(relative=relative), self.assertRaises(util.TheMasterplanError):
                    util.safe_join(Path(tmp), relative)
            for relative in (".themasterplan/state.json", "core/policy.md", "NULsafe.txt",
                             "COM10.txt", "目录/文件.md"):
                self.assertTrue(util.safe_join(Path(tmp), relative).is_relative_to(Path(tmp).resolve()))

    def test_target_file_parent_overlap_is_rejected_in_any_order(self):
        for paths in (("file", "file/nested"), ("file/nested", "file"),
                      ("core/a", "Core/b"), ("same", "same")):
            with self.subTest(paths=paths), self.assertRaises(util.TheMasterplanError):
                util.validate_target_paths(paths)

    def test_real_root_link_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real").mkdir()
            try:
                (root / "core").symlink_to(root / "real", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaises(util.TheMasterplanError):
                util.safe_join(root, "core/policy.md")


@unittest.skipIf(os.name == "nt", "POSIX permission-bit semantics")
class BoundaryPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "executable"
        self.target.write_bytes(b"before")
        self.target.chmod(0o755)

    def assert_restored(self):
        self.assertEqual(self.target.read_bytes(), b"before")
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o755)

    def test_atomic_bytes_and_json_preserve_existing_mode(self):
        util.write_bytes_atomic(self.target, b"after")
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o755)
        util.write_json_atomic(self.target, {"updated": True})
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o755)

    def test_new_file_retains_private_creation_mode(self):
        target = self.root / "new"
        util.write_bytes_atomic(target, b"new")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_caught_failure_restores_replaced_and_deleted_file_modes(self):
        real_write = util.write_bytes_atomic
        for remove in (False, True):
            with self.subTest(remove=remove):
                def fail_later(path, content, **kwargs):
                    if path.name == "later":
                        raise OSError("simulated failure")
                    return real_write(path, content, **kwargs)
                with mock.patch("tmlib.util.write_bytes_atomic", side_effect=fail_later), \
                     self.assertRaises(util.TheMasterplanError):
                    util.apply_file_changes(self.root,
                        {"executable": None if remove else b"after", "later": b"new"},
                        {"executable": b"before", "later": None})
                self.assert_restored()

    def test_failure_after_replace_restores_content_and_mode(self):
        real_write = util.write_bytes_atomic
        calls = 0
        def fail_after(path, content, **kwargs):
            nonlocal calls
            real_write(path, content, **kwargs)
            calls += 1
            if calls == 1:
                raise OSError("failure after replacement")
        with mock.patch("tmlib.util.write_bytes_atomic", side_effect=fail_after), \
             self.assertRaises(util.TheMasterplanError):
            util.apply_file_changes(self.root, {"executable": b"after"}, {"executable": b"before"})
        self.assert_restored()

    def test_concurrent_chmod_is_not_overwritten(self):
        first = self.root / "first"
        first.write_bytes(b"old")
        real_write = util.write_bytes_atomic
        def intervene(path, content, **kwargs):
            result = real_write(path, content, **kwargs)
            if path == first and content == b"new":
                self.target.chmod(0o700)
            return result
        with mock.patch("tmlib.util.write_bytes_atomic", side_effect=intervene), \
             self.assertRaises(util.TheMasterplanError):
            util.apply_file_changes(self.root, {"first": b"new", "executable": b"after"},
                                    {"first": b"old", "executable": b"before"})
        self.assertEqual(self.target.read_bytes(), b"before")
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o700)
        self.assertEqual(first.read_bytes(), b"old")

    def test_rollback_does_not_overwrite_external_permission_change(self):
        real_write = util.write_bytes_atomic
        def fail_later(path, content, **kwargs):
            if path.name == "later":
                self.target.chmod(0o700)
                raise OSError("external chmod before failure")
            return real_write(path, content, **kwargs)
        with mock.patch("tmlib.util.write_bytes_atomic", side_effect=fail_later), \
             self.assertRaisesRegex(util.TheMasterplanError, "rollback incomplete.*executable"):
            util.apply_file_changes(self.root, {"executable": b"after", "later": b"new"},
                                    {"executable": b"before", "later": None})
        self.assertEqual(self.target.read_bytes(), b"after")
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o700)


if __name__ == "__main__":
    unittest.main()
