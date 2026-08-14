---
name: themasterplan
description: >-
  TheMasterplan 单一交付责任人的轻量 AI 辅助代码交付治理协议（GitHub Flow +
  Jujutsu Profile + Generic Harness 边界）。当用户调用 /TheMasterplan，或项目
  包含根部 AGENTS.md、core/、profiles/、.themasterplan/state.json 等采用特征时使用。
---

# TheMasterplan 工作流

`/TheMasterplan` 是唯一规范的用户可见 Skill 入口。

本 Skill 是客户端薄加载入口，不复制完整规则正文，也不适配外部 orchestrator。

## 检测顺序

```text
根部 AGENTS.md
core/policy.md + core/workflow.md
治理所有权预检
profiles/<profile>.md（仅 ACTIVE）
adapters/generic.md（可选，仅 ACTIVE）
.themasterplan/state.json（采用状态，可选，仅 ACTIVE）
```

采用项目自身文件的规则优先于本 Skill 的一般说明。

## 权威来源

1. `AGENTS.md`：入口与加载顺序；
2. `core/workflow.md`：任务、治理所有权预检、验证与交接；
3. `core/policy.md`：权限、审批与发布；
4. `profiles/`：Git / jj 命令；
5. `adapters/generic.md`：普通 Harness 的薄执行边界。

## 治理所有权预检

加载 `core/workflow.md` 后，先判断当前任务是否已经由另一个交付工作流管理。

直接使用 OpenCode、Codex、ChatGPT、编辑器、Shell、Git/jj 本身不构成冲突。
如果当前调用上下文明确表明另一个系统正在管理 worker/session、task
workspace/worktree/branch、Issue→PR 生命周期、CI/review 路由，或
merge/release/deploy 工作流，则：

```text
TheMasterplan: ABSTAINED — external delivery workflow owns this task.
```

随后停止。`ABSTAINED` 不写入 `.themasterplan/state.json`，不运行更新检测或升级，不加载
外部工作流 Adapter，也不修改外部系统状态。

所有权不明确时，在任何写操作前询问人类；不得按品牌猜测。

## 内部兼容标识

以下内部实现继续保留：

- `.themasterplan/`
- `.themasterplan/bin/themasterplan.py`
- `<!-- THEMASTERPLAN:BEGIN MANAGED -->`
- `<!-- THEMASTERPLAN:END MANAGED -->`
- Python 内部 `TheMasterplanError` 等符号

这些是存储和代码兼容接口，不是用户调用命令。

## 缺失处理

缺失根部 `AGENTS.md`、`core/` 或所选 Profile 时，报告
“TheMasterplan 未完整安装”，不得静默推断完整规则。

## Pull Request 正文契约（ACTIVE 时）

创建或更新 Pull Request 前，优先读取并使用项目的
`.github/pull_request_template.md`。

若项目调用 TheMasterplan 中央 `themasterplan-check`，PR 正文至少必须包含真实 Issue
引用，或真实的明确人类授权来源、Goal、Scope；无 Issue 时不得伪造编号。

并包含非空：

```markdown
## Result
## Changes
## Verification
## Agent self-review
```

自审必须真实勾选以下 5 项：

```markdown
- [x] 满足 Issue 或明确人类授权
- [x] 没有扩大任务范围
- [x] 已阅读完整 diff
- [x] 必要验证已通过
- [x] 没有遗留调试代码、临时文件或缓存
```

未满足的项目不得虚假勾选，应先修正或如实停止。

## 更新检测（仅 ACTIVE）

确认项目完整安装且治理状态为 `ACTIVE` 后：

1. 若项目存在 `.themasterplan/state.json` 与 `.themasterplan/bin/themasterplan.py`，运行：

   ```bash
   python .themasterplan/bin/themasterplan.py check-update --root . --json
   ```

2. `CURRENT`：简短说明当前已是最新稳定版本，继续任务。
3. `UPDATE_AVAILABLE`：报告当前版本、目标版本和提交身份，由用户选择继续、
   查看变化或生成只读升级计划。
4. 未经用户明确选择，不得运行 `plan-update`。
5. 未经第二次明确批准，不得运行 `apply-update`。
6. `UNAVAILABLE`、`UNKNOWN`、`NOT_ADOPTED` 不阻断正常任务，只如实报告。
7. 更新检测不得替代 Issue、授权、范围、验证和 diff 审阅要求。
