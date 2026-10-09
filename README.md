# TheMasterplan

> Context-minimal AI-assisted delivery governance for GitHub and Jujutsu.

TheMasterplan 是一个面向代码仓库的轻量交付治理协议：让**多人按任务协作**，
明确协调人、执行者、独立审阅者与有权决策的人类；同时让 Agent 只加载当前任务
真正需要的上下文。协调人可以交接，不垄断所有人的实现、分支或审批权。

它不是 Agent 运行时、编排平台、项目管理系统或自动发布机器人。研究、实现和检查
可以由多位人类及其 Agent 并行参与。每个可合并任务有一位当前协调人维护状态，
各执行者负责自己的交付单元；团队按项目权限决定审阅、合并和发布。

**Agent 从 [AGENTS.md](AGENTS.md) 开始。人类从本文或
[采用指南](docs/adoption-guide.md) 开始。**

## 为什么是 Context-Minimal

TheMasterplan v5 的设计方向参考了 OpenAI 的
[Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)：
更强的编码 Agent 不再需要把完整规则栈、仓库地图和操作食谱预先塞进上下文。
更有效的做法是让入口保持短小、按任务渐进披露资料，并把真正需要人类判断的边界
与可以安全继续的工作区分开。

在 TheMasterplan 中，这被落实为五个原则：

- **Minimal router**：`AGENTS.md` 和 Skill 只负责告诉 Agent 什么时候读什么。
- **Progressive disclosure**：普通实现不预读 Release、Update、Policy 或无关 VCS 文档。
- **Completion contract**：实现、相关验证、修复和最终 diff 审阅完成前，不因“已有第一版”提前停下。
- **Decision boundaries**：只有范围扩大、发布、破坏性远端操作、安全风险等真实边界才需要停下。
- **Mechanical contracts**：能由模板、脚本和 CI 机械验证的规则，不重复塞进 Prompt。

因此，TheMasterplan 的目标不是教模型“每一步怎么想”，而是给它足够的项目事实、
路由信息和交付边界。

## 工作模型

```text
task
  ↓
AGENTS.md
  ↓
Context Router
  ↓
只加载当前任务需要的 workflow / policy / VCS / update 文档
  ↓
  分工 / 隔离并行 → 各单元验证 → 集成验证 → 独立审阅
  ↓
Pull Request / 已授权的微小修复快速通道
  ↓
  有权人类决定 merge / release
```

如果另一个系统已经拥有当前任务的 worker/session、workspace、PR/CI-review 或
release 生命周期，TheMasterplan 进入 `ABSTAINED`，不与外部工作流竞争治理权。
完整边界见
[docs/external-workflow-abstention.md](docs/external-workflow-abstention.md)。

多人使用同一协议、不同成员分别负责实现/审阅/审批，不构成外部治理冲突。
分工、依赖、异步授权、交接与审阅门见 [core/workflow.md](core/workflow.md)；
审批角色与授权冲突见 [core/policy.md](core/policy.md)。

## 快速采用

本源码目标为 **v5.1.0**；发布状态以 [GitHub Releases](https://github.com/OasisSaber/TheMasterplan/releases) 与对应不可变 Tag 为准。以下 v5.1.0 调用须在 Tag 发布并验证后使用；发布前只固定经审核的完整 SHA，不假定版本已发布。

推荐两种方式：

### 1. GitHub Template Repository

用本仓库作为模板创建新项目，然后：

1. 在 `AGENTS.md` 填写项目事实、默认分支和真实验证入口；
2. 保留项目自己的 `scripts/check.sh`；
3. 选择 Git 或 Jujutsu Profile；
4. 按 [采用指南](docs/adoption-guide.md) 完成 smoke test。

### 2. 现有仓库接入中央 Actions

业务仓库保留自己的验证逻辑，只调用 TheMasterplan 的中央治理工作流：

```yaml
jobs:
  check:
    name: check
    permissions:
      contents: read
    uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.1.0
    with:
      policy-ref: v5.1.0
      project-check-path: scripts/check.sh
```

业务仓库负责自己的依赖安装、lint、typecheck、test、build 与项目专属安全检查；
TheMasterplan 负责公共治理契约、PR 合规检查和调用边界。

接口细节见 [docs/actions-interface.md](docs/actions-interface.md)。

## 只在需要时读取

| 需要处理的事情 | 权威入口 |
| --- | --- |
| 普通实现、修复、文档、测试、PR | [core/workflow.md](core/workflow.md) |
| 授权、merge、release、破坏性远端操作 | [core/policy.md](core/policy.md) |
| Git 发布 / Tag | [profiles/git.md](profiles/git.md) |
| Jujutsu 发布 / Tag | [profiles/jj.md](profiles/jj.md) |
| Jujutsu 日常 change / bookmark | [jj-lifecycle.md](skills/themasterplan/references/jj-lifecycle.md) |
| adoption / update / check-update | [client-update-flow.md](docs/client-update-flow.md) |
| GitHub Actions 接口 | [actions-interface.md](docs/actions-interface.md) |
| Release 与版本通道 | [release-channels.md](docs/release-channels.md) |
| 新项目采用 | [adoption-guide.md](docs/adoption-guide.md) |
| 维护 TheMasterplan 本身 | [CONTRIBUTING.md](CONTRIBUTING.md) |

这些文档不是普通任务的默认预读清单。按任务需要加载即可。

## 一个任务如何结束

在已授权范围内，Agent 应持续工作直到以下四项全部满足：

1. 请求结果已经实现；
2. 与本次改动相关的验证通过；
3. 本次改动造成的失败已修复并复验；
4. 最终 diff 已审阅。

真正的人类决策边界出现时，报告剩余工作和所需决定，不宣称任务完成。

安全的本地读取、编辑、格式化、lint、测试、修复本次改动造成的失败和重跑相关
验证，不需要逐步请求批准。

迭代按风险运行受影响验证；push 前仍须运行完整权威入口并审阅最终 diff。
未知命令须先检查副作用，不能把生产或远端写操作当作安全本地验证。

复杂任务通常通过 Issue → change/branch → Pull Request → 人类决定 Squash Merge
交付。目标清晰且满足严格低风险条件的极小修复，可按
[core/workflow.md](core/workflow.md) 的快速通道执行。

## 验证

本仓库权威验证入口：

```bash
bash scripts/check.sh
```

PowerShell 7 可委托同一 Bash 入口：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

当前支持状态：

- **VERIFIED**：Ubuntu GitHub Actions 中的 Bash 入口，以及 PowerShell 7 委托路径。
- **PARTIAL**：macOS Bash、真实 Windows PowerShell 7 + Git for Windows；采用时应重新完成 smoke test。
- Git 文档基线：`2.34.0+`。
- Jujutsu 文档命令已按 `0.43.0` 核对；更高版本采用时应重新 smoke。

验证内容和依赖见 [scripts/README.md](scripts/README.md)。

## 更新与版本

本源码分发版本：**v5.1.0**。发布状态见上面的 Releases 链接；本文件不会仅因源码版本已更新就宣称 Release 已发布。

中文变更与升级限制见 [v5.1.0 发布说明](docs/releases/v5.1.0.md)。

普通 `/TheMasterplan` 任务不会自动检查更新。只有明确的 update、adopt、
maintenance 或版本检查意图才加载更新流程并执行只读检查。

版本通道：

- `v5.1.0`：本源码目标不可变 Release tag，使用前核验发布状态；
- `v5.0.0`：历史已发布不可变 Release tag，不移动、不覆盖；
- `v1`：冻结兼容线，不再推进；
- 完整 commit SHA：最高可复现性。

完整规则见 [docs/release-channels.md](docs/release-channels.md) 和
[docs/client-update-flow.md](docs/client-update-flow.md)。

## 非目标

TheMasterplan 不试图成为：

- 多 Agent 编排器；
- Agent runtime 或常驻服务；
- 自动 merge / release / deploy 机器人；
- 外部 orchestrator 的兼容矩阵；
- 业务项目自己的测试、构建或部署系统。

它只解决一个问题：**在 Agent 已经足够能干的前提下，用尽可能少的长期上下文，
保持交付责任、验证和人类决策边界清晰。**

## License

This project is licensed under the [MIT License](LICENSE).
