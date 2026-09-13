# TheMasterplan 采用指南

## 工具与平台基线

- Jujutsu `0.43.0` 的本文档命令已验证；更高版本采用时重新完成 smoke。
- Git `2.34.0` 或更高版本；Windows 安装包含 Git Bash 的 Git for Windows。
- `VERIFIED`：Ubuntu GitHub Actions 中的 Bash 权威入口与 PowerShell 7 委托入口。
- `PARTIAL`：macOS Bash 与真实 Windows PowerShell 7 + Git for Windows；采用时在目标平台运行 smoke。
- 文档默认远端名为 `origin`、默认分支为 `main`。采用项目不同名时统一替换。

采用前记录真实 `jj --version`、`git --version`、操作系统和验证状态。不得仅因仓库提供入口就把 `PARTIAL` 平台表述为已验证。

## v5 采用模型

v5 使用 **Context Router + Progressive Disclosure**。普通任务先读取根部 `AGENTS.md`，然后只按当前任务需要读取对应材料：

```text
普通交付                    → core/workflow.md
merge/release/破坏性操作    → core/policy.md
Git Tag / Release           → profiles/git.md
Jujutsu Tag / Release       → profiles/jj.md
Jujutsu 日常命令            → skills/themasterplan/references/jj-lifecycle.md
adopt / update              → docs/client-update-flow.md
Actions API                 → docs/actions-interface.md
外部 workflow ownership    → docs/external-workflow-abstention.md
```

不再要求普通任务预读 workflow + policy + profile + adapter 全栈；v5 也不再提供 Adapter 选择。

## 选择采用范围

### 中央调用模式（推荐）

业务仓库保留自己的项目验证入口，通过可重用工作流调用 TheMasterplan 中央治理检查。最低文件集：

```text
AGENTS.md
scripts/check.sh
.github/pull_request_template.md
.github/workflows/check.yml
```

薄调用器示例：

```yaml
name: Check

on:
  pull_request:
    branches: [main]
    types: [opened, edited, reopened, synchronize]
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  check:
    name: check
    permissions:
      contents: read
    uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.0.0
    with:
      policy-ref: v5.0.0
      project-check-path: scripts/check.sh
```

TheMasterplan 中央仓库负责工作流治理、PR 合规检查、安全基线、调用约束、并发与超时；业务仓库负责自己的依赖安装、lint、typecheck、test、build 与项目专属验证，并通过项目内 `scripts/check.sh` 暴露。

项目验证脚本必须非交互，失败返回非零状态，不依赖本机绝对路径，不读取未声明 Secret，不执行部署/发布/远端修改，并能在全新 checkout 中运行。

### 完整模板采用

推荐使用 GitHub Template Repository。最低维护集合包括：

- 根部 `AGENTS.md` 与 `CONTRIBUTING.md`；
- `core/`；
- `.github/pull_request_template.md`、`.github/workflows/` 与需要的 Issue Form；
- `scripts/` 中的权威验证入口、共享验证组件、依赖与测试；
- `docs/` 中被 Context Router 实际引用的支持文档；
- 当前采用的 VCS profile/reference。

采用者可以删除不需要的可选路径，但必须同步删除 Router 中指向它们的链接，避免留下不存在的入口。

### 仅采用 `AGENTS.md`

只复制根部 `AGENTS.md` 时，把它视为规则素材而不是完整可运行配置。必须：

1. 替换项目事实、默认分支与真实验证入口；
2. 删除或替换没有复制的 Router 链接；
3. 重新核对项目安全、架构、测试和交付资料的权威关系。

### 最小采用集合（含薄 Skill）

最小集合为：

```text
AGENTS.md
core/
所需 VCS profile/reference
项目真实验证入口
```

`skills/themasterplan/SKILL.md` 是客户端薄入口，只负责读取 `AGENTS.md` 并遵循 Context Router；仅复制 Skill 不构成完整采用。

v5 不再存在：

```text
adapters/generic.md
components.adapters
selection.adapter
--adapter
```

`ACTIVE / ABSTAINED` 是当前任务的治理所有权决策，不进入采用 selection。

任何采用方式都应记录实际来源的 Release tag 或完整 commit SHA。

## 更新检测

v5 将更新检测改为**意图驱动**。

普通 `/TheMasterplan` 任务：

```text
不自动 check-update
```

当用户或任务明确进入 adopt/update/maintenance 路径时，再读取 [client-update-flow.md](client-update-flow.md)，使用 `check-update` / `plan-update` / `apply-update`。

TheMasterplan 仍不自动升级；写入升级仍需按升级流程中的确认门执行。

## 外部交付工作流共存

TheMasterplan 不提供外部 orchestrator 专用兼容层。

- 直接使用 OpenCode、Codex、ChatGPT 等执行 Harness，不等于治理冲突；
- 若另一个系统已拥有 worker/session、task workspace/worktree/branch、Issue→PR、CI/review routing 或 merge/release/deploy 生命周期，TheMasterplan 报告 `ABSTAINED` 并停止自己的任务治理；
- 不通过品牌、版本或配置文件建立兼容矩阵。

`ABSTAINED` 不自动修改项目已有 GitHub Actions。完整边界见 [external-workflow-abstention.md](external-workflow-abstention.md)。

## 新项目

1. 使用 GitHub Template Repository 创建项目，或按上面的最小采用模式复制所需文件。
2. 填写根部 `AGENTS.md` 的项目事实、默认分支、真实验证入口和保护边界。
3. 如使用 Jujutsu，可直接 `jj git clone`，或在已有 Git clone 中执行 `jj git init --colocate`；日常命令按需读取 [jj-lifecycle.md](../skills/themasterplan/references/jj-lifecycle.md)。
4. 配置 `scripts/check.sh` 和 GitHub 保护规则。
5. 保留一个通用治理入口，避免建立第二套相互冲突的通用规则。
6. 完成一次低风险端到端演练。

## 新仓库 smoke

维护者应在全新的采用仓库中完成一次真实但低风险的演练：

- [ ] 记录 `jj --version`、`git --version`、操作系统、验证入口和初始支持状态。
- [ ] 建立 Git/Jujutsu 工作区并 fetch 最新默认分支。
- [ ] 用真实 Issue 或明确人类授权创建单独任务 change/branch/bookmark。
- [ ] 做一处容易审阅和回滚的变更，运行项目权威验证。
- [ ] 阅读完整 diff，只 push 当前任务引用。
- [ ] 创建 Pull Request，确认正文 validator 与仓库 CI 通过。
- [ ] 由人类决定是否 Squash Merge；若 Agent 获得对应明确授权，可按 `core/policy.md` 执行已授权 merge 事务。
- [ ] 合并后同步最新默认分支并完成本地清理。
- [ ] 对 Agent 自建且已合并的任务分支，只有满足 `core/policy.md` §7.1 全部条件时才可直接执行远端清理；否则回到逐次授权路径。
- [ ] 记录任务、PR、合并提交、验证结果和任何平台限制。

只有目标平台 smoke 通过后，才能把该采用项目的平台状态记录为 `VERIFIED`。

出现 conflicted ref、push 拒绝、未知远端差异、未知人工修改或范围扩大时，停止并处理真实决策边界；不得靠强推或跳过验证继续。

## 已有项目

1. 盘点现有 Agent 规则、分支保护、权限、安全、测试和交付约束。
2. 优先迁移到中央调用模式，或选择完整模板 / 最小采用集合。
3. 把 `AGENTS.md` 改成 Context Router；删除强制预读无关规则的 itinerary。
4. 删除 v4 的 generic Adapter 采用字段；v4 `adapter=generic` 由 v5 update 流程规范化移除。
5. 保留项目自身架构、安全、测试和交付资料，并按任务需要路由，而不是默认预加载。
6. 配置真实验证入口后完成低风险 smoke。

## 版本记录

```markdown
来源: TheMasterplan <release-tag-or-full-commit-sha>
采用范围: <中央调用 / 完整模板 / 最小采用集合 / 自定义文件集合>
采用日期: <YYYY-MM-DD>
首次演练任务: Issue #<number> / <human authorization reference>
Jujutsu 版本: <jj --version>
Git 版本: <git --version>
平台与验证入口: <OS / Bash / PowerShell 7>
验证状态: <VERIFIED / PARTIAL>
首次演练 PR: <URL>
```

Issue 与明确人类授权二选一。使用授权引用时，同时记录授权来源、目标和范围。来源必须填写实际使用的 Release tag 或完整 commit SHA。
