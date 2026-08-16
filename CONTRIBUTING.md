# Contributing to TheMasterplan

仅在修改工作流本身时维护本仓库。开始前读取 [AGENTS.md](AGENTS.md)，并在以下三条任务路径中选择一条。

## 支持环境

- Jujutsu `0.43.0` 的本文档命令已验证；更高版本必须在采用时重新完成烟雾测试。
- Git `2.34.0` 或更高版本；Windows 使用包含 Git Bash 的 Git for Windows。
- `VERIFIED`：Ubuntu GitHub Actions 中的 Bash 入口与 PowerShell 7 委托入口。
- `PARTIAL`：macOS Bash 与真实 Windows PowerShell 7 + Git for Windows；采用时必须在目标平台运行完整烟雾测试。
- 以下命令假设默认分支为 `main`、远端为 `origin`。采用项目使用其他名称时应一致替换。

开始前记录版本并同步远端：

```bash
jj --version
git --version
jj git fetch --remote origin
jj status
jj bookmark list --all-remotes main
jj log -r 'main | main@origin' -n 5
```

`jj git clone` 会自动跟踪默认远端 bookmark。通过 Git 克隆后再运行 `jj git init --colocate` 时，应确认 `main@origin` 已被跟踪；尚未跟踪且本地 `main` 没有独立修改时运行：

```bash
jj bookmark track 'main@origin'
jj bookmark list --tracked main
```

如果 `jj status` 或 `jj bookmark list --conflicted` 报告冲突，停止，不创建任务 change。异常处理见[同步、冲突与拒绝](#同步冲突与拒绝)。

## 复杂任务

先在 GitHub 新建 Issue 时选择唯一的[复杂任务 Issue form](.github/ISSUE_TEMPLATE/complex-task.yml)，记录目标、范围、验收条件、排除项、依赖与执行顺序：

```bash
jj new main -m "issue #<number>: <single outcome>"
jj bookmark create codex/issue-<number>-<short-name> -r @
```

## 小型低风险任务

先在当前会话中取得明确人类授权：

```bash
jj new main -m "authorized task: <single outcome>"
jj bookmark create codex/task-<short-name> -r @
```

三条路径选一。无 Issue 时不得伪造编号；创建 Pull Request 或快速通道直接合并必须记录授权来源、目标和范围。当前 Issue 或明确人类授权不能覆盖项目安全、隐私、合规、数据保护、受保护分支、发布、部署或破坏性操作限制。

## 微小修复快速通道

先在当前会话取得针对该修复的明确人类授权（不得复用其他事务的聚合授权）：

```bash
jj new main -m "authorized fast-track: <single outcome>"
jj bookmark create codex/task-<short-name> -r @
```

适用范围与判定标准见 [core/workflow.md](core/workflow.md) §1：目标清晰、无范围争议，改动为单个文件（或极少数同主题文件）、行数 ≤30，仅涉及文档/配置/测试/注释（不触及 src 核心逻辑与公共接口），不涉及持久化数据、部署、发布、远端数据或破坏性操作，权威验证入口通过、完整 diff 审阅无异常。符合时压缩为单一 commit 直接推入 `main`（不创建 Pull Request、不逐次请求审批），合并 commit 消息与一次性汇报必须记录授权来源、目标、范围。判定存疑或仓库分支保护不允许直接推送时，回退小型低风险任务路径；合并后 `main` 的 CI（若配置 push 触发）通过，否则以本地权威验证为准。

## 实现与验证

只修改任务范围内的文件，不混入或覆盖来源不明的修改。Jujutsu 没有“当前 bookmark”；任务 bookmark 会在其目标 change 被重写时自动跟随，但创建新的子 change 后不会自动前进。保持一个任务只有一个 change，并在验证前确认 bookmark 仍指向该 change：

```bash
jj status
jj bookmark list <task-bookmark>
jj log -r '@ | <task-bookmark> | main' -n 5
```

权威验证入口为：

```bash
bash scripts/check.sh
```

Windows 与 PowerShell 7 等价入口：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

当前 CI 只在 Ubuntu 上验证 Bash 与 PowerShell 委托入口。真实 Windows 或 macOS 环境在完成目标平台烟雾测试前只能标记为 `PARTIAL`。

push 前运行：

```bash
jj status
jj diff
jj diff --stat
jj log -r "main..@"
```

阅读完整 diff，确认没有范围外变更、误删、临时文件、缓存或无关生成物。验证失败时先修正并重跑。

## Push 与 Pull Request

验证和自审通过后，只 push 当前任务 bookmark：

```bash
jj git push --bookmark <task-bookmark> --remote origin
jj bookmark list --tracked <task-bookmark>
```

Jujutsu `0.43.0` 会在首次成功 push 新 bookmark 时自动建立远端跟踪。若远端 bookmark 已存在但尚未跟踪，先确认它确实属于当前任务，再运行：

```bash
jj bookmark track '<task-bookmark>@origin'
jj git fetch --remote origin
```

通过 GitHub 网页或 GitHub CLI 创建 Draft Pull Request：

```bash
gh pr create --draft --base main --head <task-bookmark>
```

Pull Request 应说明关联 Issue 或明确授权、实现结果、变更内容、验证证据、已知限制和未覆盖内容。Agent 完成自审后可以 push、创建或更新 Pull Request。只有人类可以决定是否 Squash Merge；Agent 不得未经批准 merge 或 release。发布（推进稳定分支、创建 tag、创建 Release 等）采用单一最终发布审核：授权语义见 [core/policy.md](core/policy.md)，Git 与 jj 下的安全执行方式见 [profiles/git.md](profiles/git.md) 与 [profiles/jj.md](profiles/jj.md)。

微小修复快速通道（见上文）不创建 Pull Request：会话内明确授权后，将任务 change 压缩为单一 commit 直接推入 `main` 并一次性汇报；判定存疑或仓库分支保护不允许直接推送时回退本 PR 流程。

同一 bookmark 再次 push 会更新现有 Pull Request。首次 push 后，change 已属于已发布历史；任何 restack 或内容更新都必须先取得明确人类授权，然后重新运行完整验证、阅读完整 diff，并再次 push 同一 bookmark。

## 基线前进与 Pull Request 更新

任务尚未发布且远端 `main` 前进时：

```bash
jj git fetch --remote origin
jj bookmark list --conflicted
jj log -r 'main | main@origin | @ | <task-bookmark>' -n 10
jj rebase -s @ -o main
```

任务已经 push 时，先停止并取得重写已发布历史的明确人类授权，再执行同样的 fetch 与 rebase。rebase 后如果 `jj status` 报告文件冲突，不得验证或 push；先解决文件并运行：

```bash
jj resolve --list
jj status
```

确认没有未解决冲突后，从头运行验证与自审，再 push 同一 bookmark。bookmark 会跟随被重写的任务 change，Pull Request 会更新而不是新建。

## 同步、冲突与拒绝

每次 fetch 或 push 前检查：

```bash
jj status
jj bookmark list --conflicted
jj bookmark list --all-remotes main <task-bookmark>
```

按以下边界处理：

- `main@origin` 冲突：再运行一次 `jj git fetch --remote origin`。冲突仍存在时停止，记录输出并请求人类判断；不得手工猜测远端目标。
- 本地 `main` 与 `main@origin` 分叉或 `main` 冲突：不得 push `main`，也不得擅自移动 bookmark。保留 `jj status`、`jj bookmark list --conflicted main` 和相关 `jj log` 输出，等待人类选择正确目标。
- 任务 bookmark 冲突：停止 push。由人类确认应保留的提交后，才可以使用 `jj bookmark move <task-bookmark> --to <chosen-revision> --allow-backwards`。
- push 被拒绝：不得强推。运行 `jj git fetch --remote origin`，重新检查远端 bookmark、冲突与基线；如果修复会重写已发布 change，先取得明确人类授权。
- rebase 产生文件冲突：Jujutsu 会把冲突记录在 change 中。解决并确认 `jj resolve --list` 不再列出冲突之前，不得把 change 视为可验证或可发布。

## 人工 Squash Merge 后清理

先在 GitHub 确认 Pull Request 已由人类 Squash Merge，再同步并切回最新 `main`：

```bash
jj git fetch --remote origin
jj status
jj log -r 'main | main@origin' -n 5
jj new main
```

默认只清理本地短期 bookmark，不影响远端：

```bash
jj bookmark forget <task-bookmark>
jj bookmark list --all-remotes <task-bookmark>
```

`forget` 会取消本地 bookmark 及其跟踪关系，不会把远端删除排入下一次 push。如果 GitHub 已在人类合并时删除远端分支，下一次 fetch 会同步该状态。

已合并任务分支的远端删除属于 PR 生命周期收尾（core/policy.md §7.1）：满足全部豁免条件（Agent 为任务创建、已合并进默认分支、无开放 PR 引用、不涉 tag/Release/他人分支/强推）时无需另行授权；任一条件不满足，仍须另一次单独、明确的人类决定。远端清理路径：

```bash
jj bookmark delete <task-bookmark>
jj git push --deleted --remote origin --dry-run
jj git push --deleted --remote origin
```

必须阅读 dry-run 的完整输出；如果包含目标以外的任何待删除 bookmark，停止。Agent 不得把合并授权或普通 push 授权解释为远端删除授权；已合并任务分支清理仅限 core/policy.md §7.1 列明的豁免条件，删除后以 `git ls-remote` 验证 ref 消失并记录。

## Pull Request 自审

创建或更新 Pull Request 前确认：

- 当前 change 和 bookmark 只对应一个任务；
- 基线来自最近一次 fetch 后无冲突的 `main`；
- 权威验证通过，完整 diff 已阅读；
- PR 正文记录真实验证结果、限制和未覆盖内容；
- 未执行 merge、release、远端删除或未经授权的已发布历史重写。

Jujutsu bookmark 与 push 的详细语义以[官方 bookmark 文档](https://docs.jj-vcs.dev/latest/bookmarks/)和[官方 CLI reference](https://docs.jj-vcs.dev/latest/cli-reference/)为准；本文件只描述本仓库在 Jujutsu `0.43.0` 上核对过的单 change 生命周期，更高版本采用前必须重新验证命令语义。

## 中央接口变更

本仓库同时维护治理规范与[中央 Actions 接口](docs/actions-interface.md)。中央接口变更视为公共 API 变更，`v1` 生命周期内不得移动工作流路径、删除或重命名输入、更改默认项目验证入口、更改 required check 公共名称、新增 Secret 或写权限。

修改公共接口前必须：

1. 对照 [docs/actions-interface.md](docs/actions-interface.md) 判断变更是否破坏 `v1` 承诺；破坏性调整只允许在下一主版本进行；
2. 判断版本处理：不改变通过/失败结果的修复为 patch；新增可选输入或非阻断诊断为 minor；新增会让现有消费者失败的规则或重命名工作流、Job、输入、PR 字段为下一主版本；新增权限、Secret 或部署行为需要单独安全审查；
3. 在独立[消费者 smoke 仓库](docs/release-channels.md)完成真实调用验证后再发布；
4. Release tag 经人类批准后创建为不可变 annotated tag；`v1` 兼容线已冻结（2026-08-02），不再推进、不创建新 v1.x tag；
5. Agent 未经批准不得创建 Release 或修改 GitHub Ruleset。
