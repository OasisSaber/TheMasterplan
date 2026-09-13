# GitHub Actions 中央接口

TheMasterplan 提供集中维护、版本化发布的 GitHub Actions 可重用工作流。业务仓库通过 `uses` 调用，不复制中央 CI 实现。

## 工作流路径

v1 兼容线（冻结，`policy-ref` 默认 `v1`）：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/aw-check.yml@v1
```

当前版（v5.0.0，tag-only 精确固定）：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.0.0
with:
  policy-ref: v5.0.0
```

`aw-check.yml` 在 v1 兼容线生命周期内不得移动或重命名。当前版工作流路径是 `themasterplan-check.yml`；已发布路径与 Tag 不移动。

## 输入

只允许以下 `workflow_call` 输入：

| 输入 | 类型 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `project-check-path` | string | `scripts/check.sh` | 调用项目权威验证入口 |
| `policy-ref` | string | `v1` | TheMasterplan 策略脚本版本 |

不得加入任意 `setup-command`、`check-command`、Shell 表达式、Secret 输入、发布或部署参数、自动合并参数或写权限开关。

固定当前版调用时 `policy-ref` 必须等于 `uses` 引用版本；v5.0.0 通道显式指定 `policy-ref: v5.0.0`。v1 冻结兼容线保持独立路径和默认 `policy-ref: v1`。

## 固定行为

- Runner：`ubuntu-latest`
- 权限：`contents: read`
- 超时：15 分钟
- PR 正文检查：必须执行
- `AGENTS.md`：调用方仓库根部必须存在
- 项目验证入口：必须存在、受 Git 跟踪、不得是符号链接
- Secrets：不接受
- 部署/发布：不执行
- required check：对外稳定

## 调用链

```text
业务仓库 .github/workflows/check.yml
        │ uses @v1（aw-check.yml）或 @v5.0.0（themasterplan-check.yml）
        ▼
TheMasterplan reusable workflow
        │
        ├── 检出调用方仓库
        ├── 检出 TheMasterplan 策略实现
        ├── 验证 TheMasterplan 采用契约
        ├── 验证 Pull Request 正文
        ├── 运行调用方 project-check-path
        └── 输出稳定状态检查
```

TheMasterplan 仓库自身通过相对路径调用当前提交内的 reusable workflow，确保 PR 测试当前 PR 中的策略实现而不是远端旧版本。

## 职责边界

TheMasterplan 决定触发、采用契约、PR 合规、安全权限和中央工作流版本；业务仓库决定依赖、lint、typecheck、test、build 与项目专属安全检查。

v5 的 Context-Minimal Reform 不改变这个 Actions 公共接口。Prompt/Skill 的 progressive disclosure 与 CI 机械契约是两层独立机制。

## PR 契约

继续以 `scripts/validate_pr_body.py` 与 `.github/pull_request_template.md` 为机械单一事实来源：

- Issue 与明确人类授权二选一；
- Issue 使用单个关闭引用；
- 明确授权包含来源、目标和范围；
- `Result`、`Changes`、`Verification` 不为空；
- 五项 Agent 自审全部勾选。

Skill、OpenCode command 与 `AGENTS.md` 不再复制这些字段清单。Agent 在 PR 任务中按 Context Router 读取/使用模板，CI 负责机械验证。

`v1` 内以下标题仍是冻结公共接口：

```text
## Related task
## Result
## Changes
## Verification
## Agent self-review
## Notes for human
```

## 消费者契约

调用方仓库必须满足 `scripts/validate_consumer.py` 机械验证的最小采用契约：

- 仓库根目录存在；
- 根部存在 `AGENTS.md`；
- `project-check-path` 非空且是安全 POSIX 相对路径；
- 路径不含反斜杠或 `..`；
- 目标是普通文件、不是符号链接；
- 目标受 Git 跟踪。

不强制 `AGENTS.md` 内容、技术栈、Issue 真实性、测试覆盖率、依赖版本、构建命令、发布流程或部署策略。

## 兼容政策

v1 冻结线允许不破坏既有调用的修复，但不推进 ref。当前版通过不可变 SemVer Tag 发布。

禁止未经主版本迁移直接改变：工作流路径、输入名/必填语义、默认项目验证入口、required check 公共名称、Secret/写权限要求或 PR 机械契约；不得加入自动 merge/release/deploy。

## 安全边界

- reusable workflow 与调用器只授予 `contents: read`；
- 不使用 `secrets: inherit`，不声明 Secret；
- 不使用 `pull_request_target`；
- checkout 设置 `persist-credentials: false`；
- 第三方 Action 固定到完整 commit SHA；
- 项目验证路径不可为绝对路径、不可包含 `..`、不可为符号链接、必须受 Git 跟踪；
- 不通过 `eval` 执行输入，不拼接任意命令；
- 不自动 merge、release、deploy，不修改调用仓库；
- 不向 PR 代码暴露凭据。

## 故障回退

消费者在坏版本出现时临时固定上一正常 Release tag 或完整 SHA，等待 TheMasterplan 发布前向修复；`v1` 兼容线继续冻结，不 force push 或重写已发布历史。
