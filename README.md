# TheMasterplan

A minimal AI-assisted workflow with a single delivery owner for GitHub and Jujutsu.

TheMasterplan 是面向个人开发者的“单一交付责任人的 AI 辅助代码交付治理协议”，并提供集中维护、版本化发布的 GitHub Actions 可重用工作流接口。

它不是 Agent 服务、多 Agent 编排平台、Web/API 服务、Agent 运行时、自动发布机器人或项目管理系统；不自动 merge 或 release。允许研究、实现、检查子代理与多个模型参与，但只能有一个主交付责任人控制最终范围、VCS、最终验证、push、Pull Request、发布授权执行与人类交接。

v5 采用 **Context-Minimal / Progressive Disclosure**：Agent 先读取根部 `AGENTS.md` 的 Context Router，只在任务需要时再读取对应 Core、VCS、发布、更新或采用文档；普通任务不再预读整套规则，也不自动执行更新检测。

## 稳定接口

| 用途 | 入口 |
| --- | --- |
| Agent Context Router | [AGENTS.md](AGENTS.md) |
| 人类入口 | [README.md](README.md) |
| 维护入口 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 日常交付治理 | [core/workflow.md](core/workflow.md) |
| 授权与发布边界 | [core/policy.md](core/policy.md) |
| 采用指南 | [docs/adoption-guide.md](docs/adoption-guide.md) |
| 外部工作流共存边界 | [docs/external-workflow-abstention.md](docs/external-workflow-abstention.md) |
| 更新检测与升级流程 | [docs/client-update-flow.md](docs/client-update-flow.md) |
| 验证入口 | `bash scripts/check.sh` |
| Actions 接口 | [docs/actions-interface.md](docs/actions-interface.md) |
| 版本通道 | [docs/release-channels.md](docs/release-channels.md) |
| 复制接口 | GitHub Template Repository |
| 版本接口 | Git tag / GitHub Release |

## 支持与验证状态

- `VERIFIED`：Ubuntu GitHub Actions 中的 Bash 权威入口，以及 PowerShell 7 委托同一 Bash 入口的路径。
- `PARTIAL`：macOS Bash 与真实 Windows PowerShell 7 + Git for Windows 环境；仓库提供入口和采用 smoke，但当前 CI 不在这些原生平台运行。
- Jujutsu：文档命令以 `0.43.0` 为基线；更高版本采用时重新 smoke。
- Git：文档假设 `2.34.0` 或更高版本。

外部交付工作流共存采用**主动退让**而不是持续适配：普通 OpenCode/Codex 等执行 Harness 可以直接使用 TheMasterplan；一旦另一个系统已经拥有当前任务的 worker/session、workspace、PR/CI-review 或发布生命周期，本任务状态为 `ABSTAINED`，TheMasterplan 不再施加自己的任务工作流，也不维护该系统的专用兼容层。边界见 [docs/external-workflow-abstention.md](docs/external-workflow-abstention.md)。

## v5 Context Router

普通任务的默认入口只有根部 `AGENTS.md`。它根据任务意图按需路由：

```text
普通实现 / 文档 / 测试 / PR  → core/workflow.md
merge / release / 破坏性操作 → core/policy.md
Git Tag / Release             → profiles/git.md
Jujutsu Tag / Release         → profiles/jj.md
Jujutsu 日常命令              → skills/themasterplan/references/jj-lifecycle.md
adopt / update                → docs/client-update-flow.md
Actions API                   → docs/actions-interface.md
外部 workflow ownership      → docs/external-workflow-abstention.md
```

不要因为某份规则文件存在就预加载它。机械契约继续由 PR 模板、validator、Manifest、state 校验和 GitHub Actions 执行。

TheMasterplan 的 Completion Contract 是：在已授权范围内持续执行，直到请求结果已实现、相关验证通过、本次修改造成的失败已修复并复验、最终 diff 已审阅；只有到达真正的人类决策边界时才停止。

## 采用方式

### 完整模板

推荐通过 GitHub Template Repository 创建新仓库。完整模板提供 Context Router、Core、验证入口、GitHub 工作流和人类文档；采用后仍应按项目实际情况填写项目事实、验证命令和保护规则。

### 仅采用通用规则

可以只摘取根部 `AGENTS.md` 作为设计参考，但它不是无需修改即可独立运行的配置文件。若 Router 指向的文件没有一并采用，应删除或替换对应链接，不得把不存在的验证入口或治理文档声明为有效。

### 最小采用集合（含薄 Skill）

最小采用集合为：根部 `AGENTS.md`、`core/`、选定 VCS 所需的 `profiles/`/reference，以及项目真实验证入口。`skills/themasterplan/SKILL.md` 是极薄的客户端入口，只负责读取 `AGENTS.md` 并遵循 Context Router；仅复制 Skill 不构成完整采用。

v5 不再提供 Adapter 选择。`ACTIVE / ABSTAINED` 是任务级治理所有权判断，不进入项目采用选择。

更新检测改为**意图驱动**：普通 `/TheMasterplan` 任务不会自动执行 `check-update`；只有用户或任务进入 adopt/update/maintenance 路径时才读取 [docs/client-update-flow.md](docs/client-update-flow.md) 并使用更新命令。

所有采用方式都应按[采用指南](docs/adoption-guide.md)记录实际使用的 Release tag 或完整 commit SHA，而不是默认写入固定版本号。

## 快速开始

1. 使用 GitHub Template Repository 创建完整模板仓库，或按[采用指南](docs/adoption-guide.md)选择最小采用方式。
2. 在 `AGENTS.md` 的“项目事实”中填写项目目标、默认分支、真实验证入口与保护边界。
3. 如使用 Jujutsu，可选择直接 `jj git clone`，或在已有 Git clone 中 `jj git init --colocate`；日常命令按需读取 [jj-lifecycle.md](skills/themasterplan/references/jj-lifecycle.md)。
4. 按项目需要替换验证脚本和持续集成配置，并按 [仓库设置说明](docs/repository-settings.md) 由人类配置 GitHub 保护规则。
5. 复杂任务使用[复杂任务 Issue form](.github/ISSUE_TEMPLATE/complex-task.yml)记录边界；小型低风险任务可使用当前会话中的明确人类授权。
6. 完成实现、相关验证与最终 diff 审阅后，通过 Pull Request 交给人类决定是否 Squash Merge；符合 [core/workflow.md](core/workflow.md) §1 的微小修复可走快速通道。

## 本仓库验证

```bash
bash scripts/check.sh
```

PowerShell 7 可使用委托同一 Bash 权威入口的等价命令：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

当前 GitHub Actions 在 Ubuntu 上运行仓库权威验证。真实 Windows 与 macOS 支持状态为 `PARTIAL`，采用者应在目标平台完成 smoke 后再声明为已验证。

验证入口检查 Python 语法、单元测试、Markdown 内部链接、Shell/YAML 语法及仓库机械契约。依赖说明见 [scripts/README.md](scripts/README.md)。

## 中央 Actions 接口

业务仓库通过可重用工作流调用中央治理检查：

```yaml
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

v1 冻结兼容线消费者继续使用 `aw-check.yml@v1`（`policy-ref` 保持默认 `v1`）。当前版调用要求 `uses ref == policy-ref`；完整契约见 [docs/actions-interface.md](docs/actions-interface.md)，版本通道见 [docs/release-channels.md](docs/release-channels.md)。

TheMasterplan 负责工作流治理、PR 合规检查、安全基线与调用约束；业务仓库负责自己的依赖安装、lint、typecheck、test、build 等专属验证，并通过项目验证入口暴露。

## 维护边界

日常采用本工作流时，不在本仓库为业务项目创建 Issue。只有修改 TheMasterplan 本身时，才在本仓库记录维护任务。

Agent 可以在已记录范围内实现、验证、push 和维护 Pull Request，但 merge、release 和破坏性远端操作仍按 `core/policy.md` 的真实决策边界执行。

## 来源

TheMasterplan 整理自 [OasisSaber/agentic-project-workflow](https://github.com/OasisSaber/agentic-project-workflow) 的最终接受基线。

历史研发记录保留在旧仓库。

基线提交：`ee0482d08ea6859bef2d1c06f37fa97bb25a575f`

## License

This project is licensed under the [MIT License](LICENSE).
