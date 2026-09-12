# TheMasterplan

A minimal AI-assisted workflow with a single delivery owner for GitHub and Jujutsu.

TheMasterplan 是面向个人开发者的“单一交付责任人的 AI 辅助代码交付治理协议”（GitHub Flow + Jujutsu 适配），并提供集中维护、版本化发布的 GitHub Actions 可重用工作流接口。

它不是 Agent 服务、多 Agent 编排平台、Web 或 API 服务、CLI 产品、Agent 运行时、自动发布机器人、项目管理系统；不自动 merge 或 release。允许研究/实现/检查子代理与多个模型参与，但只能有一个主交付责任人控制任务最终范围、VCS、最终验证、push、Pull Request、发布授权执行与人类交接。

## 稳定接口

| 用途 | 入口 |
| --- | --- |
| Agent 入口 | [AGENTS.md](AGENTS.md) |
| 人类入口 | [README.md](README.md) |
| 维护入口 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 采用指南 | [docs/adoption-guide.md](docs/adoption-guide.md) |
| 外部工作流共存边界 | [docs/external-workflow-abstention.md](docs/external-workflow-abstention.md) |
| 更新检测与升级流程 | [docs/client-update-flow.md](docs/client-update-flow.md) |
| 完整任务生命周期 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 验证入口 | `bash scripts/check.sh` |
| Actions 接口 | [docs/actions-interface.md](docs/actions-interface.md) |
| 版本通道 | [docs/release-channels.md](docs/release-channels.md) |
| 复制接口 | GitHub Template Repository |
| 版本接口 | Git tag / GitHub Release |

## 支持与验证状态

- `VERIFIED`：Ubuntu GitHub Actions 中的 Bash 权威入口，以及 PowerShell 7 委托同一 Bash 入口的路径。
- `PARTIAL`：macOS Bash 与真实 Windows PowerShell 7 + Git for Windows 环境；仓库提供入口和采用烟雾测试，但当前 CI 不在这些原生平台运行。

外部交付工作流共存采用**主动退让**而不是持续适配：普通 OpenCode/Codex 等
执行 Harness 可以直接使用 TheMasterplan；一旦另一个系统已经拥有当前任务的
worker/session、workspace、PR/CI-review 或发布生命周期，本任务状态为
`ABSTAINED`，TheMasterplan 不再施加自己的任务工作流，也不维护该系统的专用
兼容层。边界见 [docs/external-workflow-abstention.md](docs/external-workflow-abstention.md)。
- Jujutsu：本文档命令已使用 `0.43.0` 核对；更高版本不是自动验证范围，采用时必须重新运行烟雾测试。
- Git：文档假设 `2.34.0` 或更高版本。
- 示例默认远端为 `origin`、受保护分支为 `main`。

## 采用方式

### 完整模板

推荐通过 GitHub Template Repository 创建新仓库。完整模板的最小维护集合包括根部 `AGENTS.md`、`CONTRIBUTING.md`、`.github/`、`scripts/` 与 `docs/`；这些文件共同提供任务规则、Pull Request/Issue 入口、验证命令和采用说明。

### 仅采用通用规则

可以只摘取根部 `AGENTS.md`，但它不是无需修改即可独立运行的配置文件。采用者必须先替换“项目事实”和验证命令，并删除或替换没有一并复制的仓库内链接与 PowerShell 入口。不得把不存在的 `scripts/check.sh` 或支持文档继续声明为有效入口。

### 最小采用集合（含薄 Skill）

v5 的最小采用集合为：根部 `AGENTS.md`、`core/`、选定的 VCS Profile/
参考文件，以及 [skills/themasterplan](skills/themasterplan/SKILL.md)。

Skill 只是最小 Context Router，不复制完整工作流，也不在普通任务开始时自动
预读 Policy、Release、Update 或 VCS 文档。Agent 先读取 `AGENTS.md`，再按
Context Router 只加载当前任务需要的材料。仅复制 Skill 仍不构成完整采用。

采用者须填写项目事实、配置真实验证命令与 GitHub 保护，并按
[采用指南](docs/adoption-guide.md)完成烟雾测试。更新检测只在明确的
update/adopt/maintenance 意图下按
[client-update-flow.md](docs/client-update-flow.md)执行。

所有采用方式都应按[采用指南](docs/adoption-guide.md)记录实际使用的 Release tag 或 commit SHA，而不是默认写入固定版本号。

## 快速开始

1. 使用 GitHub Template Repository 创建完整模板仓库；若只采用 `AGENTS.md`，先按上面的“仅采用通用规则”边界完成定制。
2. 在本地初始化 Jujutsu 工作区；二选一：

   ```bash
   # 路径 A：直接使用 Jujutsu 克隆
   jj git clone <repository-url>
   cd <repository>
   ```

   ```bash
   # 路径 B：仓库已通过 Git 克隆
   git clone <repository-url>
   cd <repository>
   jj git init --colocate
   ```

   初始化后运行：

   ```bash
   jj --version
   git --version
   jj status
   jj git remote list
   jj log -r 'main | main@origin' -n 5
   ```

3. 在 `AGENTS.md` 的“项目事实”中填写项目目标、技术栈、验证命令和默认分支。
4. 按项目需要替换验证脚本和持续集成配置，并按 [仓库设置说明](docs/repository-settings.md) 由人类配置 GitHub 保护规则。
5. 开始新任务前运行 `jj git fetch` 同步远端基线；初始化后才能使用本工作流规定的 `jj status`、`jj new` 和 bookmark 命令。
6. 复杂任务使用[复杂任务 Issue form](.github/ISSUE_TEMPLATE/complex-task.yml)记录边界；小型低风险任务仍使用当前会话中的明确人类授权。
7. 使用一个 jj change 完成实现、验证与 Agent 自审，通过 Pull Request 交给人类决定是否 Squash Merge；微小修复可走快速通道（[core/workflow.md](core/workflow.md) §1）直接合并。

从同步、创建 change、跟踪与 push bookmark、更新 Pull Request，到人工 Squash Merge 后清理的完整命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。遇到 `main`、`main@origin` 或任务 bookmark 冲突时停止，不要强推或猜测目标。

## 本仓库验证

```bash
bash scripts/check.sh
```

PowerShell 7 可使用委托同一 Bash 权威入口的等价命令：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

当前 GitHub Actions 在 Ubuntu 上同时运行上述 Bash 和 PowerShell 委托入口。真实 Windows 与 macOS 支持状态为 `PARTIAL`，采用者必须在目标平台完成[新仓库烟雾测试](docs/adoption-guide.md#新仓库烟雾测试)后再声明为已验证。

验证入口检查 Python 语法、Pull Request 正文校验器单元测试，以及 Markdown 内部链接、Shell 脚本提交模式、YAML 语法和 Shell 语法。依赖说明见 [scripts/README.md](scripts/README.md)。

## 中央 Actions 接口

业务仓库通过可重用工作流调用中央治理检查，不再复制 TheMasterplan 的 CI 实现：

```yaml
jobs:
  check:
    name: check
    permissions:
      contents: read
    uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v4.1.0
    with:
      policy-ref: v4.1.0
      project-check-path: scripts/check.sh
```

v1 兼容线消费者继续使用 `aw-check.yml@v1`（`policy-ref` 保持默认 `v1`），
见 [docs/release-channels.md](docs/release-channels.md)。

TheMasterplan 负责工作流治理、PR 合规检查、安全基线与调用约束；业务仓库负责自己的
依赖安装、lint、typecheck、test、build 等专属验证，并通过项目内
`scripts/check.sh` 暴露。接口契约见
[docs/actions-interface.md](docs/actions-interface.md)，版本通道见
[docs/release-channels.md](docs/release-channels.md)。

## 维护边界

日常采用本工作流时，不在本仓库为业务项目创建 Issue。只有修改 TheMasterplan 工作流本身时，才在本仓库记录维护任务。

Agent 可以在已记录范围内实现、验证、push 和维护 Pull Request，但未经人类批准不得 merge 或 release；发布事务的聚合授权语义见 [core/policy.md](core/policy.md)。

## 来源

TheMasterplan 整理自
[OasisSaber/agentic-project-workflow](https://github.com/OasisSaber/agentic-project-workflow)
的最终接受基线。

历史研发记录保留在旧仓库。

基线提交：`ee0482d08ea6859bef2d1c06f37fa97bb25a575f`

## License

This project is licensed under the [MIT License](LICENSE).
