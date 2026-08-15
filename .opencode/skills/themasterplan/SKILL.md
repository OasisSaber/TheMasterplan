---
name: themasterplan
description: Load TheMasterplan rules for direct OpenCode delivery work.
compatibility: Requires AGENTS.md, core/, and the selected profile.
---

# TheMasterplan for OpenCode

Use this Skill when OpenCode is the direct execution Harness for a repository
that has adopted TheMasterplan, or when the user invokes `/themasterplan`.

OpenCode 本身不是外部治理冲突。加载 canonical `themasterplan` Skill 与
`core/workflow.md` 后先执行治理所有权预检。

If the invocation context clearly shows that an external delivery workflow
already owns worker/session, task workspace/worktree/branch, PR/CI-review
routing, or merge/release/deploy lifecycle, report:

```text
TheMasterplan: ABSTAINED — external delivery workflow owns this task.
```

and stop TheMasterplan. Do not run update checks or apply TheMasterplan task
lifecycle rules in `ABSTAINED`.

When `ACTIVE`, before any write operation verify and read:

1. AGENTS.md
2. core/workflow.md
3. core/policy.md
4. the selected profiles/<profile>.md
5. adapters/generic.md when present

If a required file is missing, report “TheMasterplan 未完整安装” and stop.
Do not silently infer missing rules.

加载 canonical Skill 后执行其 `ACTIVE` 更新检测步骤；检测到更新时等待用户
选择，不得自动生成或应用升级。

Before creating or updating a Pull Request, use
`.github/pull_request_template.md` when present. For repositories using
TheMasterplan `themasterplan-check`, the PR body must contain a real Issue reference or
explicit human authorization and non-empty sections:

```markdown
## Result
## Changes
## Verification
## Agent self-review
```

The self-review must truthfully include:

```markdown
- [x] 满足 Issue 或明确人类授权
- [x] 没有扩大任务范围
- [x] 已阅读完整 diff
- [x] 必要验证已通过
- [x] 没有遗留调试代码、临时文件或缓存
```

Do not invent an Issue or check an item that is not true.

When `ACTIVE`, run the authoritative validation before every push and read the
complete diff before creating or updating the Pull Request. Do not merge,
release, deploy, delete remote resources, force-push published history, modify
unrelated tasks, or expand scope without the required human authorization.
