# Jujutsu 日常 change / bookmark 参考

> 仅在任务需要 Jujutsu 命令时读取。本文件提供命令，不复制授权与发布 Policy。
> 权限边界以 `core/policy.md` 为准；任务完成标准以 `core/workflow.md` 为准。
> 以下命令在 Jujutsu `0.43.0` 上核对。

## 初始化

```bash
jj git clone <repository-url>
# 或
git clone <repository-url>
cd <repository>
jj git init --colocate
```

已有 Git clone 转 colocated workspace 后确认默认远端 bookmark：

```bash
jj bookmark track 'main@origin'
jj bookmark list --tracked main
```

仅在尚未跟踪且本地 `main` 没有独立修改时执行。

## 同步与状态

```bash
jj --version
git --version
jj git fetch --remote origin
jj status
jj bookmark list --conflicted
jj bookmark list --all-remotes main
jj log -r 'main | main@origin' -n 5
```

存在无法判断的 bookmark/ref 冲突时停止，不猜测目标。

## 创建任务 change

复杂任务：

```bash
jj new main -m "issue #<number>: <single outcome>"
jj bookmark create codex/issue-<number>-<short-name> -r '@'
```

明确授权的小任务：

```bash
jj new main -m "authorized task: <single outcome>"
jj bookmark create codex/task-<short-name> -r '@'
```

一个任务保持一个 change。无 Issue 时不得伪造编号。

## 实现、验证与 diff

```bash
jj status
jj bookmark list <task-bookmark>
jj log -r '@ | <task-bookmark> | main' -n 5

bash scripts/check.sh

jj diff
jj diff --stat
jj log -r 'main..@'
```

项目验证命令以根部 `AGENTS.md` 为准；上面的 `scripts/check.sh` 是
TheMasterplan 默认示例。

## Push

```bash
jj git push --bookmark <task-bookmark> --remote origin
jj bookmark list --tracked <task-bookmark>
```

远端 bookmark 已存在但未跟踪时，先确认它属于当前任务，再：

```bash
jj bookmark track '<task-bookmark>@origin'
jj git fetch --remote origin
```

## 基线前进

未发布的任务 change 可在确认远端状态后：

```bash
jj git fetch --remote origin
jj bookmark list --conflicted
jj log -r 'main | main@origin | @ | <task-bookmark>' -n 10
jj rebase -s @ -o main
```

若 change 已 push，是否允许重写已发布历史按 `core/policy.md` 决定。冲突解决后
重新运行相关验证和最终 diff 审阅。

## 常见冲突

- `main@origin` 冲突：再次 fetch；仍冲突则停止并报告状态。
- 本地 `main` 与 `main@origin` 分叉：不擅自移动或 push `main`。
- 任务 bookmark 冲突：在正确目标明确前不 push。
- push 被拒绝：fetch 并检查差异；不要强推。
- rebase 文件冲突：使用 `jj resolve --list` / `jj status` 确认解决后再验证。

## 合并后本地清理

确认 PR 已合并后：

```bash
jj git fetch --remote origin
jj new main
jj bookmark forget <task-bookmark>
jj bookmark list --all-remotes <task-bookmark>
```

远端任务分支是否可直接删除由 `core/policy.md` §7.1 决定；满足豁免条件时先
dry-run、再删除、最后用 `git ls-remote` 验证 ref 已消失。不要在这里维护第二套
授权规则。

## 发布

Tag / Release 不使用本文件。按 Context Router 读取 `core/policy.md`、
`profiles/jj.md` 和 `profiles/git.md`。
