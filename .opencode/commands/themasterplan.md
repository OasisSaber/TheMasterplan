---
description: Load and follow TheMasterplan delivery workflow
---

Use the native `skill` tool to load the `themasterplan` Skill.

Do not continue until the Skill confirms required TheMasterplan files are
present and completes the governance-ownership preflight.

Direct OpenCode use can remain `ACTIVE`. If the current invocation is already
owned by an external delivery workflow, report:

```text
TheMasterplan: ABSTAINED — external delivery workflow owns this task.
```

and stop TheMasterplan. Do not run update detection or impose TheMasterplan
task/PR/reaction/cleanup rules while `ABSTAINED`.

When `ACTIVE`, the required load order is:

- AGENTS.md
- core/workflow.md
- core/policy.md
- the selected profiles/<profile>.md
- adapters/generic.md when present

加载 canonical Skill 后执行其 `ACTIVE` 更新检测步骤；检测到更新时等待用户选择；
不得自动生成或应用升级。

Before creating or updating a Pull Request, follow the canonical Skill's PR body
contract and `.github/pull_request_template.md` when present. Do not invent an
Issue or claim validation that did not run.

Run authoritative project validation before every push. Read the complete diff
before creating or updating the Pull Request. Report failed or unexecuted
validation truthfully.

Additional task context:

$ARGUMENTS
