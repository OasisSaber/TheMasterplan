# GitHub Actions 中央接口

本源码目标为 **v5.1.0**；发布状态以 [GitHub Releases](https://github.com/OasisSaber/TheMasterplan/releases) 与对应不可变 Tag 为准。以下 v5.1.0 调用须在 Tag 发布并验证后使用；发布前只固定经审核的完整 SHA，不假定版本已发布。

TheMasterplan 提供集中维护、版本化发布的 GitHub Actions 可重用工作流。
业务仓库通过 `uses` 调用，不再复制中央 CI 实现。

## 工作流路径

v1 兼容线（冻结，`policy-ref` 默认 `v1`）：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/aw-check.yml@v1
```

本源码目标版本（v5.1.0，tag-only 精确固定）：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.1.0
with:
  policy-ref: v5.1.0
```

`aw-check.yml` 在 v1 兼容线生命周期内不得移动或重命名。工作流路径移动属
公共 API 变更，只能在下一主版本执行；v4.0.0 已随改名
（aw-check.yml → themasterplan-check.yml）执行。

## 输入

第一版只允许以下 `workflow_call` 输入：

| 输入 | 类型 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `project-check-path` | string | `scripts/check.sh` | 调用项目权威验证入口 |
| `policy-ref` | string | `v1` | TheMasterplan 策略脚本版本 |

不得加入任意 `setup-command`、`check-command`、Shell 表达式、Secret 输入、
发布或部署参数、自动合并参数或写权限开关。

固定版本调用时 `policy-ref` 必须等于 `uses` 引用版本（v5.1.0 通道必须
显式指定 `policy-ref: v5.1.0`），见 [release-channels.md](release-channels.md)。

## 固定行为

第一版固定：

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
        │ uses @v1（aw-check.yml）或 @v5.1.0（themasterplan-check.yml）
        ▼
TheMasterplan reusable workflow
        │
        ├── 检出调用方仓库
        ├── 检出 TheMasterplan 策略实现
        ├── 验证 TheMasterplan 采用契约
        ├── 验证 Pull Request 正文
        ├── 运行调用方 scripts/check.sh
        └── 输出稳定状态检查
```

TheMasterplan 仓库自身通过相对路径调用当前提交内的 reusable workflow，确保 TheMasterplan 的 PR
测试当前 PR 中的策略实现而不是远端旧版本。

## 职责边界

TheMasterplan 决定如何触发、如何验证采用契约、如何检查 PR 合规性、如何限制权限、如何
报告结果以及如何管理中央工作流版本；业务仓库决定安装哪些依赖、运行哪些测试、
如何构建以及如何执行项目专属安全检查。

## PR 契约

继续复用 `scripts/validate_pr_body.py` 与 `.github/pull_request_template.md`：

- Issue 与明确人类授权二选一；
- Issue 使用单个关闭引用；
- 明确授权包含来源、目标和范围；
- `Result`、`Changes`、`Verification` 不为空；
- 五项 Agent 自审全部勾选。

`v1` 内以下标题视为公共接口，不得直接删除、重命名或改变其必填语义：

```text
## Related task
## Result
## Changes
## Verification
## Agent self-review
## Notes for human
```

如需改变契约，先增加兼容验证、提供迁移文档，并在下一主版本执行破坏性调整。

### v5.1.0 协作记录扩展

工作树新增 `Collaboration` 记录节；出现时由正文 validator 校验模式、角色、
候选 SHA、审阅状态/证据及依赖/交接。旧格式 PR 无此节继续通过，原必填标题与
自审项不变；中央 Actions 输入、权限和 required check 名称不变。

正文只验证**声明结构**，不验证成员身份、权限、证据 URL 的真实性，或声明 SHA
是否等于实际 head。它不是 GitHub approving review，也不是 merge/release 授权。
独立审阅与实时门禁按 [仓库设置](repository-settings.md) 和 Core 执行。
`Mode` 与任务 Issue/授权的一致性、Contributors 是否涵盖全部实际实现者，也须
人工或平台证据核实；结构门不读取 Issue 权限或证明这些声明真实。填 solo 不是
团队义务的豁免，模式冲突时不能因为 CI 绿色而交付。

新采用项目可以显式要求协作记录，使用
`python scripts/validate_pr_body.py --require-collaboration <pr-body-file>`；此可选
CLI 严格入口不是新增中央 Actions 输入。脚本不在受管文件清单内，项目须显式
维护可达副本与调用，不能假定已安装。维护者在项目自己的验证中启用前，应先
迁移模板和既有开放 PR，不无迁移期地收紧历史消费者。

已发布 `v5.0.0` 不会获得工作树扩展，也不移动 tag。采用扩展须选择含改动的完整
commit SHA 或核验已发布的 v5.1.0，并审阅更新计划；此兼容扩展不声称仅靠版本标记就已发布。

TheMasterplan 仓库自身在项目拥有的 `scripts/check.sh` 中，对 PR 事件读取
`GITHUB_EVENT_PATH` 并启用严格入口。删除整节也会失败；非 PR 本地检查通过测试
覆盖此结构门，但不声称已核验真实审阅。该要求不改变中央工作流的历史消费者默认。

## 消费者契约

调用方仓库必须满足最小采用契约（由 `scripts/validate_consumer.py` 机械验证）：

- 仓库根目录存在；
- 根部存在 `AGENTS.md`；
- `project-check-path` 非空；
- `project-check-path` 是 POSIX 相对路径；
- 路径不含反斜杠、不含 `..`；
- 目标是普通文件、不是符号链接；
- 目标受 Git 跟踪。

第一版不强制 `AGENTS.md` 内容、技术栈、Issue 真实性、测试覆盖率、依赖版本、
构建命令、发布流程或部署策略。

## 兼容政策

`v1` 内允许：修复错误、改善日志、增加不阻断的诊断、增加带默认值的可选输入、
更新固定的第三方 Action SHA、改善性能、修复误报、改善文档、增加测试覆盖。

`v1` 内禁止：更改 v1 兼容线内 reusable workflow 路径（aw-check.yml）；删除或重命名输入；更改默认项目
验证入口；更改 required check 公共名称；新增 Secret 要求或写权限；自动
merge、release 或 deploy；修改 PR 必填标题；修改自审项文本导致现有调用失败；
引入新的破坏性失败条件；把 Ubuntu required check 直接替换为其他平台；无
迁移期地收紧项目契约。

## 安全边界

- reusable workflow 与调用器只授予 `contents: read`；
- 不使用 `secrets: inherit`，不声明 Secret；
- 不使用 `pull_request_target`；
- checkout 设置 `persist-credentials: false`；
- 第三方 Action 固定到完整 commit SHA；
- 项目验证路径不可为绝对路径、不可包含 `..`、不可为符号链接、必须受 Git
  跟踪；
- 不通过 `eval` 执行输入，不拼接任意命令；
- 不自动 merge、release、deploy，不修改调用仓库，不删除远端 bookmark；
- 不向 PR 代码暴露凭据。

## 故障回退

消费者在坏版本出现时临时固定上一正常 Release tag 或完整 SHA，等待 TheMasterplan 发布
前向修复；`v1` 兼容线已冻结（2026-08-02），不再快进，修复通过新版本通道
发布（见 [release-channels.md](release-channels.md)）。不使用 force push 回写
历史。
