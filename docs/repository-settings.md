# GitHub 仓库设置

GitHub Template Repository 只复制仓库文件，不能保证这些服务器端设置被复制。每次从模板创建仓库后，必须由人类检查并配置：

- `main` 只能通过 Pull Request 修改，并要求 required check 状态检查通过。
- 禁止 force push 和删除 `main`。
- `v1` 分支（中央 Actions 接口兼容分支）已冻结（2026-08-02，指向承载 v2.0.0 内容的提交）：禁止推进、force push、删除、Agent 凭据更新或直接在 `v1` 开发。
- 尽可能禁止管理员、GitHub App 和自动化绕过规则。
- 只启用 Squash Merge，并禁用 auto-merge。
- Actions 调用权限：reusable workflow 与调用器只授予 `contents: read`，不传递 Secrets，不使用 `pull_request_target`。
- Agent 凭据不得拥有 admin、merge 或 release 权限。

仓库文件中的规则不能替代 GitHub 服务器端保护；这些设置不由本模板自动配置。

## 团队审阅与权限

在项目事实中记录范围/merge/release/deploy 的有权人类角色，以及 Agent 可以
执行的动作。用实际成员的独立凭据操作，不共享账号或凭据；CODEOWNERS、权限
与 Ruleset 的配置/变更须另有明确授权，不能从任务或 PR 创建授权推导。

团队采用者须配置并核验：至少一位有资格的独立 approving reviewer、required
CI、blocking conversation/review 的处理规则，以及新候选的重新审阅。GitHub 可
要求 required reviews、dismiss stale approvals，以及由非最后推送者批准最新
reviewable push；可按模块配置 CODEOWNERS。支持情况按仓库类型/套餐实核，不将
模板文字当作服务器端设置已生效。

依据：[GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
和 [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)。

合并前读取当前 PR head、真实 review（审阅者、状态与 commit）、CI 和保护门：
并核对任务 Issue/授权模式与 PR 一致、实际实现者未从 Contributors 漏记。
作者自审、bot/子代理意见、正文的 `Review: complete` 或证据链接本身均不等于
required approval。dismissed/stale approval、候选变化、有效 changes requested、
未知权限或平台门未满足时不合并；不替审阅者 dismiss，不自动降低人数或 bypass。
有权人类批准 merge 也不能覆盖这些限制。

本次文件改革只提供协议与记录校验，未配置或验证任何采用项目的实际 Ruleset、
团队成员权限或真实 approving review。采用演练必须补齐这些平台证据。

## Required check

reusable workflow 在 GitHub UI 中最终显示的名称不能假定为纯 `check`。迁移 required check 时，先在独立消费者 smoke 仓库运行新工作流并记录真实 check-run 名称，然后按以下顺序由人类执行：

真实 check-run 名称：**`themasterplan-check / check`**（已在消费者 smoke 仓库 `OasisSaber/TheMasterplan-consumer-smoke` 经真实运行验证，结论 success；Issue 4/7 汇报见 TheMasterplan Issue #45）。

迁移记录（已完成，2026-08-02）：

1. ✅ 现有 Ruleset 保留旧 required check，过渡期同时运行旧检查与新检查；
2. ✅ 将 `themasterplan-check / check` 加入 required checks（规则集 `Protect main`）；
3. ✅ 创建测试 PR（TheMasterplan #50），确认新旧检查均满足；
4. ✅ 移除旧 required check `check`（规则集现仅要求 `themasterplan-check / check`）；
5. ✅ 删除旧 CI 实现（TheMasterplan `.github/workflows/check.yml` 中旧 `check` job，PR #51）。

当前状态：TheMasterplan 仓库 required check 仅 `themasterplan-check / check`，`check.yml` 仅含相对路径调用的 `themasterplan-check` job。消费方仓库（如 linshe-marketplace-miniapp）如需启用 required check，按自身实测 check-run 名称（调用方 job 名决定）执行上述迁移。
