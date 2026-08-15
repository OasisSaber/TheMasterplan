# Generic Adapter：薄 Harness 边界

> 本文件只说明 TheMasterplan 如何在**没有其他交付工作流接管任务**时由普通
> Agent Harness 执行。它不是 orchestrator 兼容层。

## 1. ACTIVE 条件

以下工具可以作为执行 Harness，而不自动构成治理冲突：

- OpenCode / Codex / ChatGPT 等直接执行环境；
- 编辑器、Shell；
- Git / Jujutsu；
- lint、test、build 工具。

前提是这些工具没有另外拥有当前任务的 worker/session、workspace、PR、CI
reaction、merge/release/deploy 生命周期。

## 2. 外部治理介入

一旦有明确证据表明另一个系统已经拥有上述任一交付生命周期，按
`core/workflow.md` §0：

```text
TheMasterplan: ABSTAINED — external delivery workflow owns this task.
```

然后停止 TheMasterplan 任务工作流。

不得为了继续运行而：

- 读取或改写外部 orchestrator 配置；
- 维护外部工具版本特例；
- 映射 reaction / claim / worker reuse；
- 与外部系统竞争 task/worktree/PR 状态所有权。

## 3. ACTIVE 时的通用映射

| TheMasterplan | 普通 Harness |
|---|---|
| Issue / 明确授权 | 当前任务上下文 |
| 单一任务 change | 当前任务分支或工作区 |
| 权威验证入口 | Harness 调用项目验证命令 |
| 完整 diff 审阅 | Harness 的 diff/read 工具 |
| Pull Request | GitHub PR 或项目声明的审查对象 |
| CI 通过门 | PR 关联 CI 全部通过后再通知用户“PR 待你合并” |
| 人类最终门 | merge / release / destructive action 前的明确决定 |

Harness 只负责执行，不复制 Core 规则正文。

## 4. 边界

- 本 Adapter 不改变 `core/policy.md`；
- 不改变 `profiles/` 的 Git/jj 命令；
- 不维护外部工作流兼容层；
- 不因为某个 Harness 存在就自动 `ABSTAINED`；
- 判断依据始终是当前任务是否已经有另一个交付治理所有者。
