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
