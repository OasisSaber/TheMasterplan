#!/usr/bin/env python3
"""Mechanically validate the TheMasterplan pull request template."""

import os
import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDERS = ("<number>",)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
ISSUE = re.compile(
    r"(?:close(?:s|d)?|fix(?:es|ed)?|resolve(?:s|d)?)\s+#\d+",
    re.IGNORECASE,
)
HEADERS = ("Result", "Changes", "Verification", "Agent self-review")
REQUIRED_REVIEW_ITEMS = (
    "满足 Issue 或明确人类授权",
    "没有扩大任务范围",
    "已阅读完整 diff",
    "必要验证已通过",
    "没有遗留调试代码、临时文件或缓存",
)
COLLABORATION_FIELDS = (
    "Mode", "Coordinator", "Contributors", "Reviewer", "Candidate",
    "Review", "Evidence", "Dependencies", "Handoff",
)
IDENTITY = re.compile(r"(?:@[A-Za-z0-9][A-Za-z0-9-]*|[A-Za-z0-9][A-Za-z0-9_.:-]*)")
FULL_SHA = re.compile(r"[0-9a-fA-F]{40}")
UNASSIGNED = {"none", "unassigned", "not-required", "pending"}


def identity_key(value):
    return value.lower().removeprefix("@")


def validate_collaboration(body, required=False):
    """Validate declared records only, never authenticate a review or permission."""
    headings = re.findall(r"(?m)^## Collaboration[ \t]*$", body)
    if not headings:
        return ["Collaboration is required for this project."] if required else []
    if len(headings) != 1:
        return ["Use exactly one Collaboration section."]
    content = section(body, "Collaboration") or ""
    if re.search(r"(?m)^[ \t]*(?:`{3,}|~{3,})", content):
        return ["Collaboration records must not be hidden in code fences."]
    values, errors = {}, []
    for field in COLLABORATION_FIELDS:
        matches = re.findall(rf"(?m)^- {field}:[ \t]*(.*)$", content)
        if len(matches) != 1 or not matches[0].strip():
            errors.append(f"Collaboration requires one nonempty {field}.")
        else:
            values[field] = matches[0].strip()
            if "<" in values[field] or ">" in values[field]:
                errors.append(f"Remove Collaboration placeholder from {field}.")
    if errors:
        return errors
    if values["Mode"] not in ("solo", "team"):
        errors.append("Collaboration Mode must be solo or team.")
    for field in ("Coordinator", "Reviewer"):
        if not IDENTITY.fullmatch(values[field]):
            errors.append(f"Collaboration {field} requires a stable identity.")
    if identity_key(values["Coordinator"]) in UNASSIGNED:
        errors.append("Coordinator must be assigned.")
    raw_contributors = [part.strip() for part in values["Contributors"].split(",")]
    contributors = [identity_key(part) for part in raw_contributors]
    if (not all(IDENTITY.fullmatch(part) for part in raw_contributors)
            or len(set(contributors)) != len(contributors)
            or any(part in UNASSIGNED for part in contributors)):
        errors.append("Contributors must be distinct stable identities, comma-separated.")
    if values["Review"] not in ("pending", "complete", "not-required"):
        errors.append("Review must be pending, complete or not-required.")
    if values["Mode"] == "team":
        if values["Review"] == "not-required":
            errors.append("Team work cannot waive independent review.")
    if identity_key(values["Reviewer"]) in contributors:
        errors.append("Reviewer must be independent of Contributors.")
    if values["Candidate"] != "pending" and not FULL_SHA.fullmatch(values["Candidate"]):
        errors.append("Candidate must be a full commit SHA or pending.")
    if values["Review"] == "complete":
        if identity_key(values["Reviewer"]) in UNASSIGNED:
            errors.append("Complete review requires an assigned Reviewer.")
        if not FULL_SHA.fullmatch(values["Candidate"]):
            errors.append("Complete review requires the full reviewed candidate SHA.")
        if not re.fullmatch(r"https://\S+", values["Evidence"]):
            errors.append("Complete review requires an HTTPS evidence reference.")
    return errors


def section(body, heading):
    match = re.search(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", body)
    return match.group(1).strip() if match else None


def validate(body, require_collaboration=False):
    errors = []
    visible_body = HTML_COMMENT.sub("", body)
    issue = re.search(r"(?m)^- Issue:[ \t]*(.*)$", visible_body)
    source = re.search(r"(?m)^  - Authorization source:[ \t]*(.*)$", visible_body)
    goal = re.search(r"(?m)^  - Goal:[ \t]*(.*)$", visible_body)
    scope = re.search(r"(?m)^  - Scope:[ \t]*(.*)$", visible_body)
    issue_value = issue.group(1).strip() if issue else ""
    authorization = [match.group(1).strip() if match else "" for match in (source, goal, scope)]

    for placeholder in PLACEHOLDERS:
        if placeholder in issue_value:
            errors.append(f"Remove template placeholder text from Issue: {placeholder}.")
    has_issue = bool(issue_value)
    has_authorization = any(authorization)
    if has_issue == has_authorization:
        errors.append("Fill exactly one of Issue or explicit human authorization.")
    if has_issue and not ISSUE.fullmatch(issue_value):
        errors.append(
            "Issue must be one closing reference such as Closes #123."
        )
    if has_authorization:
        for name, value in zip(("Authorization source", "Goal", "Scope"), authorization):
            if not value:
                errors.append(f"Explicit human authorization requires {name}.")

    for heading in HEADERS[:3]:
        content = section(visible_body, heading)
        if not content:
            errors.append(f"{heading} must not be empty.")
    review = section(visible_body, "Agent self-review") or ""
    for item in REQUIRED_REVIEW_ITEMS:
        checked = re.search(rf"(?m)^- \[[xX]\] {re.escape(item)}$", review)
        present = re.search(rf"(?m)^- \[[ xX]\] {re.escape(item)}$", review)
        if not checked:
            errors.append(
                f"Agent self-review item must be checked: {item}."
                if present else f"Agent self-review item is missing: {item}."
            )
    errors.extend(validate_collaboration(visible_body, require_collaboration))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body_file", nargs="?")
    parser.add_argument("--event-file", help="Read the PR body from a GitHub event JSON file")
    parser.add_argument("--require-collaboration", action="store_true")
    args = parser.parse_args()
    if args.body_file and args.event_file:
        parser.error("body_file and --event-file are mutually exclusive")
    if args.event_file:
        try:
            event = json.loads(Path(args.event_file).read_text(encoding="utf-8"))
            body = event["pull_request"]["body"]
            if not isinstance(body, str):
                raise ValueError("pull_request.body must be a string")
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f"Unable to read PR event: {error}")
    elif args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    else:
        body = os.environ["PR_BODY"] if "PR_BODY" in os.environ else sys.stdin.read()
    errors = validate(body, args.require_collaboration)
    if errors:
        print("Pull Request body validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Pull Request body is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
