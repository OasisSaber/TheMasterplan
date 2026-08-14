import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/themasterplan-check.yml"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class StringKeyLoader(yaml.SafeLoader):
    pass


StringKeyLoader.add_implicit_resolver(
    "tag:yaml.org,2002:str",
    re.compile(r"^(?:on|off|yes|no|true|false|y|n)$", re.IGNORECASE),
    list("onOffyesfTRUEYN"),
)


def load_workflow():
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=StringKeyLoader)
    if True in data:
        data["on"] = data.pop(True)
    return data


class ActionsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = load_workflow()
        cls.check = cls.workflow["jobs"]["check"]
        cls.checkout_steps = [
            step
            for step in cls.check["steps"]
            if step.get("uses", "").startswith("actions/checkout@")
        ]
        cls.step_sources = [
            step.get("uses", "")
            for step in cls.check["steps"]
            if step.get("uses")
        ]

    def test_workflow_call_trigger(self):
        self.assertIn("workflow_call", self.workflow["on"])

    def test_job_id_is_check(self):
        self.assertIn("check", self.workflow["jobs"])

    def test_job_name_is_check(self):
        self.assertEqual(self.check.get("name"), "check")

    def test_top_level_permissions_read_only(self):
        self.assertEqual(
            self.workflow.get("permissions", {}).get("contents"), "read"
        )
        self.assertEqual(len(self.workflow["permissions"]), 1)

    def test_no_pull_request_target(self):
        self.assertNotIn("pull_request_target", self.workflow.get("on", {}))

    def test_no_secrets_inherit(self):
        self.assertNotIn("secrets", self.workflow)
        for job in self.workflow["jobs"].values():
            self.assertNotIn("secrets", job)

    def test_no_write_all(self):
        self.assertNotEqual(self.workflow.get("permissions"), "write-all")

    def test_no_write_permissions(self):
        permissions = self.workflow.get("permissions", {})
        for name, value in permissions.items():
            self.assertNotEqual(value, "write")
        for job in self.workflow["jobs"].values():
            job_permissions = job.get("permissions", {})
            for name, value in job_permissions.items():
                self.assertNotEqual(value, "write")

    def test_checkout_persist_credentials_false(self):
        self.assertTrue(self.checkout_steps, "no checkout steps found")
        for step in self.checkout_steps:
            self.assertEqual(
                step.get("with", {}).get("persist-credentials"), False
            )

    def test_third_party_actions_pinned_to_full_sha(self):
        self.assertTrue(self.step_sources, "no action steps found")
        for source in self.step_sources:
            reference = source.split("@", 1)[1]
            self.assertRegex(reference, FULL_SHA)

    def test_default_project_check_path(self):
        self.assertEqual(
            self.workflow["on"]["workflow_call"]["inputs"]["project-check-path"][
                "default"
            ],
            "scripts/check.sh",
        )

    def test_default_policy_ref(self):
        self.assertEqual(
            self.workflow["on"]["workflow_call"]["inputs"]["policy-ref"]["default"],
            "v1",
        )

    def test_timeout_not_above_fifteen_minutes(self):
        self.assertLessEqual(self.check.get("timeout-minutes", 15), 15)

    def test_caller_path_is_project(self):
        paths = [
            step.get("with", {}).get("path")
            for step in self.checkout_steps
            if step.get("with", {}).get("path")
        ]
        self.assertIn("project", paths)
        self.assertEqual(paths[0], "project")

    def test_policy_path_is_themasterplan(self):
        paths = [
            step.get("with", {}).get("path")
            for step in self.checkout_steps
            if step.get("with", {}).get("path")
        ]
        self.assertIn(".themasterplan", paths)

    def test_runner_is_ubuntu_latest(self):
        self.assertEqual(self.check.get("runs-on"), "ubuntu-latest")


if __name__ == "__main__":
    unittest.main()
