import unittest
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from validate_pr_body import REQUIRED_REVIEW_ITEMS, validate


REVIEW = "\n".join(f"- [x] {item}" for item in REQUIRED_REVIEW_ITEMS)
BASE = f"""## Related task
- Issue: Closes #1
- Explicit human authorization:
  - Authorization source:
  - Goal:
  - Scope:

## Result
Done.

## Changes
Changed files.

## Verification
Tests passed.

## Agent self-review
{REVIEW}
"""

COLLABORATION = """\n## Collaboration
- Mode: team
- Coordinator: @alice
- Contributors: @alice, @bob
- Reviewer: @carol
- Candidate: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- Review: complete
- Evidence: https://github.com/example/project/pull/1#pullrequestreview-1
- Dependencies: none
- Handoff: none
"""


class CollaborationRecordTests(unittest.TestCase):
    def test_team_record_and_legacy_compatibility(self):
        self.assertEqual(validate(BASE), [])
        self.assertEqual(validate(BASE + COLLABORATION), [])
        self.assertEqual(validate(BASE + COLLABORATION, require_collaboration=True), [])
        self.assertTrue(validate(BASE, require_collaboration=True))

    def test_draft_is_pending_not_a_claim_of_completed_review(self):
        body = COLLABORATION.replace("Reviewer: @carol", "Reviewer: unassigned")
        body = body.replace("Review: complete", "Review: pending")
        body = body.replace("Candidate: " + "a" * 40, "Candidate: pending")
        body = body.replace("Evidence: https://github.com/example/project/pull/1#pullrequestreview-1", "Evidence: pending")
        self.assertEqual(validate(BASE + body), [])

    def test_solo_record_cannot_override_native_required_reviews(self):
        body = COLLABORATION.replace("Mode: team", "Mode: solo")
        body = body.replace("Reviewer: @carol", "Reviewer: not-required")
        body = body.replace("Review: complete", "Review: not-required")
        self.assertEqual(validate(BASE + body), [])

    def test_independence_case_and_handle_alias(self):
        for reviewer in ("@alice", "@Alice", "alice", "@bob"):
            with self.subTest(reviewer=reviewer):
                self.assertTrue(validate(BASE + COLLABORATION.replace("Reviewer: @carol", "Reviewer: " + reviewer)))

    def test_non_implementing_coordinator_can_review(self):
        # Independence is from implementation, not a mandatory third person.
        body = COLLABORATION.replace("Contributors: @alice, @bob", "Contributors: @bob")
        body = body.replace("Reviewer: @carol", "Reviewer: @alice")
        self.assertEqual(validate(BASE + body), [])

    def test_unassigned_coordinator_and_contributors(self):
        for field in ("Coordinator: @alice", "Contributors: @alice, @bob"):
            for value in ("pending", "none", "<identity>"):
                with self.subTest(field=field, value=value):
                    self.assertTrue(validate(BASE + COLLABORATION.replace(field, field.split(":")[0] + ": " + value)))

    def test_duplicate_roles_fields_and_sections(self):
        for extra in ("- Mode: team\n", "- Coordinator: @bob\n", COLLABORATION):
            self.assertTrue(validate(BASE + COLLABORATION + extra))
        self.assertTrue(validate(BASE + COLLABORATION.replace("@alice, @bob", "@alice, Alice")))

    def test_missing_or_hidden_fields(self):
        for field in ("Mode", "Coordinator", "Contributors", "Reviewer", "Candidate", "Review", "Evidence", "Dependencies", "Handoff"):
            lines = COLLABORATION.splitlines()
            selected = next(line for line in lines if line.startswith("- " + field + ":"))
            for replacement in ("", "<!-- " + selected + " -->", "- " + field + ": <!-- hidden -->"):
                with self.subTest(field=field, replacement=replacement):
                    self.assertTrue(validate(BASE + COLLABORATION.replace(selected, replacement)))

    def test_complete_review_requires_candidate_identity_and_evidence(self):
        for before, after in (("Reviewer: @carol", "Reviewer: unassigned"),
                              ("Candidate: " + "a" * 40, "Candidate: pending"),
                              ("Candidate: " + "a" * 40, "Candidate: aaaaaaa"),
                              ("Evidence: https://github.com/example/project/pull/1#pullrequestreview-1", "Evidence: pending"),
                              ("Review: complete", "Review: approved")):
            with self.subTest(after=after):
                self.assertTrue(validate(BASE + COLLABORATION.replace(before, after)))

    def test_team_cannot_waive_review_or_hide_record_in_fence(self):
        self.assertTrue(validate(BASE + COLLABORATION.replace("Review: complete", "Review: not-required")))
        hidden = COLLABORATION.replace("## Collaboration", "## Collaboration\n```text") + "\n```\n"
        self.assertTrue(validate(BASE + hidden))

    def test_cli_strict_env_stdin_file_and_event(self):
        command = [sys.executable, str(Path(__file__).with_name("validate_pr_body.py"))]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("PR_BODY", None)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            body_file = root / "body.md"
            event_file = root / "event.json"
            body_file.write_text(BASE + COLLABORATION, encoding="utf-8")
            event_file.write_text(json.dumps({"pull_request": {"body": BASE + COLLABORATION}}), encoding="utf-8")
            cases = [
                ([], BASE, env, 0),
                (["--require-collaboration"], BASE, env, 1),
                (["--require-collaboration"], "", dict(env, PR_BODY=BASE + COLLABORATION), 0),
                ([str(body_file), "--require-collaboration"], "", dict(env, PR_BODY=BASE), 0),
                (["--event-file", str(event_file), "--require-collaboration"], "", env, 0),
                ([str(body_file), "--event-file", str(event_file)], "", env, 2),
            ]
            for args, stdin, case_env, expected in cases:
                with self.subTest(args=args, expected=expected):
                    result = subprocess.run(command + args, input=stdin, env=case_env,
                                            capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(result.returncode, expected, result.stderr)
            for event in ({}, {"pull_request": {"body": None}}, {"pull_request": []}):
                event_file.write_text(json.dumps(event), encoding="utf-8")
                result = subprocess.run(command + ["--event-file", str(event_file)],
                                        input="", env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)


class ValidatePrBodyTests(unittest.TestCase):
    def test_valid_issue(self): self.assertEqual([], validate(BASE))
    def test_valid_closing_issue_keywords(self):
        for value in ("Fixes #12", "Resolves #345", "closed #6"):
            with self.subTest(value=value):
                self.assertEqual([], validate(BASE.replace("Closes #1", value)))

    def test_valid_authorization(self):
        body = BASE.replace("Closes #1", "").replace("  - Authorization source:\n  - Goal:\n  - Scope:", "  - Authorization source: chat\n  - Goal: fix\n  - Scope: scripts")
        self.assertEqual([], validate(body))

    def test_html_comment_is_allowed(self): self.assertEqual([], validate("<!-- 二选一，删除不适用项。 -->\n" + BASE))
    def test_hidden_issue_reference_does_not_pass(self):
        body = BASE.replace("Closes #1", "<!-- Closes #1 -->")
        self.assertTrue(validate(body))

    def test_both_paths(self): self.assertTrue(validate(BASE.replace("  - Authorization source:", "  - Authorization source: chat")))
    def test_no_paths(self): self.assertTrue(validate(BASE.replace("Closes #1", "")))
    def test_placeholder(self): self.assertTrue(validate(BASE.replace("#1", "#<number>")))
    def test_placeholder_text_outside_issue_field_is_allowed(self):
        for body in (
            BASE.replace("Changed files.", "Changed literal `<number>` handling."),
            BASE + "\n## Notes for human\nThe template uses `<number>` as an example.\n",
            BASE.replace("Tests passed.", "```text\n<number>\n```\nTests passed."),
        ):
            with self.subTest(body=body):
                self.assertEqual([], validate(body))

    def test_empty_sections(self):
        for heading in ("Result", "Changes", "Verification"):
            content = {"Result":"Done.", "Changes":"Changed files.", "Verification":"Tests passed."}[heading]
            with self.subTest(heading=heading):
                self.assertTrue(validate(BASE.replace(f"## {heading}\n{content}", f"## {heading}")))

    def test_comment_only_sections_are_empty(self):
        for heading in ("Result", "Changes", "Verification"):
            content = {"Result":"Done.", "Changes":"Changed files.", "Verification":"Tests passed."}[heading]
            with self.subTest(heading=heading):
                body = BASE.replace(
                    f"## {heading}\n{content}",
                    f"## {heading}\n<!-- hidden content -->",
                )
                self.assertTrue(validate(body))

    def test_missing_review_item(self): self.assertTrue(validate(BASE.replace(f"- [x] {REQUIRED_REVIEW_ITEMS[0]}\n", "")))
    def test_unrelated_review_item_does_not_pass(self): self.assertTrue(validate(BASE.replace(REVIEW, "- [x] Reviewed")))
    def test_review_item_unchecked(self): self.assertTrue(validate(BASE.replace(f"[x] {REQUIRED_REVIEW_ITEMS[0]}", f"[ ] {REQUIRED_REVIEW_ITEMS[0]}")))
    def test_hidden_checked_review_item_does_not_pass(self):
        item = REQUIRED_REVIEW_ITEMS[0]
        body = BASE.replace(f"- [x] {item}", f"<!-- - [x] {item} -->")
        self.assertTrue(validate(body))

    def test_authorization_fields(self):
        for field in ("Authorization source: chat", "Goal: fix", "Scope: scripts"):
            body = BASE.replace("Closes #1", "").replace("  - Authorization source:\n  - Goal:\n  - Scope:", "  - Authorization source: chat\n  - Goal: fix\n  - Scope: scripts").replace(field, field.split(":")[0] + ":")
            self.assertTrue(validate(body))

    def test_hidden_authorization_does_not_pass(self):
        body = BASE.replace("Closes #1", "").replace(
            "  - Authorization source:\n  - Goal:\n  - Scope:",
            "  - Authorization source: <!-- chat -->\n"
            "  - Goal: <!-- fix -->\n"
            "  - Scope: <!-- scripts -->",
        )
        self.assertTrue(validate(body))

    def test_invalid_issue_values(self):
        for value in (
            "not-an-issue",
            "reviewed in #123",
            "#123",
            "Closes #1 and fixes #2",
            "Closes owner/repository#123",
        ):
            with self.subTest(value=value):
                self.assertTrue(validate(BASE.replace("Closes #1", value)))


if __name__ == "__main__":
    unittest.main()
