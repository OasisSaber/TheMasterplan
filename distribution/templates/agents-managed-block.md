<!-- THEMASTERPLAN:BEGIN MANAGED -->
# TheMasterplan

This block is the project Context Router. Load guidance only when the task needs it.

- routine delivery: `core/workflow.md`
- authorization / merge / release / destructive remote action: `core/policy.md`
- VCS release/tag: load the selected `profiles/<profile>.md` from `.themasterplan/state.json`
- Jujutsu daily change/bookmark commands: `skills/themasterplan/references/jj-lifecycle.md`
- adoption/update: `docs/client-update-flow.md`

External delivery ownership is defined in `core/workflow.md` §0; do not add a separate orchestrator compatibility layer.

Do not preload the whole rule stack.

Within the authorized scope, continue until the requested result exists, relevant
validation passes, failures caused by the change are fixed and revalidated, and
the final diff is reviewed — or until a genuine human decision boundary is reached.
<!-- THEMASTERPLAN:END MANAGED -->

## 项目事实

<!-- 在此维护项目名、目标、默认分支、验证入口、受保护分支和项目特定约束。
     TheMasterplan apply/update 只管理上方区块。 -->
