# Contributing to TheMasterplan

仅在修改 TheMasterplan 本身时维护本仓库。Agent 从根部 `AGENTS.md` 的 Context Router 开始，不预读全部治理文档。

## 开始任务

先确认：

```text
任务来源：Issue 或当前会话明确授权
工作区：无来源不明的修改
远端：默认分支/ref 状态明确
范围：单一、可验证
```

普通实现、文档、测试与 PR 交付只需读取 `core/workflow.md`。只有真正涉及 merge、release、破坏性远端操作或已发布历史重写时才读取 `core/policy.md`。

如果使用 Jujutsu，日常 change/bookmark 命令按需读取 `skills/themasterplan/references/jj-lifecycle.md`；不要因为仓库支持 jj 就在每个任务预载完整 Release profile。

## 三类任务路径

### 复杂任务

使用 GitHub Issue 记录目标、范围、验收条件和排除项，再创建单一任务 change/branch。

### 小型低风险任务

当前会话中的明确人类授权可以定义目标与范围。无 Issue 时不得伪造编号。普通情况下仍走 PR。

### 微小修复快速通道

仅在 `core/workflow.md` §1 全部条件满足时使用：目标清晰、极小、低风险、约 ≤30 行、只涉及文档/配置/测试/注释、不触及核心逻辑/公共接口/数据/发布/破坏性操作，并且验证与最终 diff 正常。

需要针对此修复的明确授权；不满足任一条件或分支保护不允许直接推送时回退普通 PR 路径。

## 默认继续与 Completion Contract

在已授权范围内，安全的本地工作默认继续：

```text
读取相关文件
实现/编辑
格式化、lint、测试
修复本次改动造成的失败
重跑受影响验证
检查最终 diff
准备 PR/交付材料
```

不要在第一次实现后仅因为“可以让人 review”而提前停下。完成标准来自 `AGENTS.md`：结果实现、相关验证通过、本次改动造成的问题已修复并复验、最终 diff 已审阅，或出现真正需要人类决定的边界。

## 验证

本仓库权威验证入口：

```bash
bash scripts/check.sh
```

PowerShell 7 委托入口：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

push 前运行权威验证并审阅完整 diff。验证失败时修复由本次改动造成的问题并重跑；不得把失败或未执行验证表述为通过。

## Pull Request

普通 PR 使用仓库 `.github/pull_request_template.md`。模板与 `scripts/validate_pr_body.py` 是 PR 正文机械契约的单一事实来源；不要在其他文档复制字段清单。

创建或更新 PR 后：

1. 等待关联 CI；
2. 本次修改导致 CI 失败时继续修复并重跑；
3. CI 通过后再报告 PR 已准备好供人类决定是否合并；
4. merge 是否可由 Agent 执行取决于 `core/policy.md` 中是否已有对应明确授权，不把“人类最终决定”误解为“人类必须亲自点击”。

## 基线前进与冲突

未发布任务可在确认远端状态后安全 rebase/restack。任务已经 push 后，任何会重写已发布历史的操作都属于决策边界，应按 `core/policy.md` 处理。

以下情况停止，不猜测：

- 默认分支/ref 冲突且正确目标不明确；
- push 被拒且修复需要强推或重写已发布历史；
- 未知人工修改会被覆盖；
- 任务范围需要实质扩大。

不要 force push 掩盖状态差异。

## 合并后清理

Agent 自建任务分支在满足 `core/policy.md` §7.1 全部条件时，可以作为 PR 生命周期收尾直接清理；否则需要新的明确授权。

清理前执行对应 VCS 的 dry-run，确认没有目标以外的待删除 ref；删除后使用 `git ls-remote` 或等价只读检查验证远端 ref 已消失。

Jujutsu 具体命令见 `skills/themasterplan/references/jj-lifecycle.md`。

## 发布与公共接口

发布/Tag 任务才加载：

```text
core/policy.md
docs/release-channels.md
profiles/git.md 或 profiles/jj.md
```

中央 Actions 接口变更同时读取 `docs/actions-interface.md`。

发布仍使用单一最终授权门：准备与只读审核 → 人类一次决定 → 已批准范围内连续执行 → 远端验证。未经发布授权不得创建/推送发布 Tag 或 GitHub Release；不得移动已有 Tag、推进冻结 `v1` 或 force push。

v5 Context-Minimal Reform 改变 Agent 的上下文加载模型和采用 schema，但不借机扩大 Actions 权限、Secret、merge/release 自动化或部署能力。

## 支持环境

- Jujutsu 文档基线：`0.43.0`；更高版本采用时重新 smoke。
- Git：`2.34.0+`。
- Ubuntu GitHub Actions 路径为 `VERIFIED`；真实 Windows/macOS 在完成目标平台 smoke 前保持 `PARTIAL`。

## 最终原则

> 规则按需披露，机械契约交给代码验证；Agent 在已授权范围内持续完成任务，只在真实决策边界停止。
