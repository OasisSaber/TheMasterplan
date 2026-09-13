# TheMasterplan

> Context-minimal AI-assisted delivery governance for GitHub and Jujutsu.

TheMasterplan 是一个面向代码仓库的轻量交付治理协议：让 **一个主交付责任人**
控制最终范围、VCS、验证、Pull Request 与发布交接，同时让 Agent 只加载当前任务
真正需要的上下文。

它不是 Agent 运行时、编排平台、项目管理系统或自动发布机器人。研究、实现和检查
可以由多个模型或子代理参与，但最终交付仍由一个责任人收敛。

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
实现 → 相关验证 → 修复失败 → 最终 diff
  ↓
Pull Request / 已授权的微小修复快速通道
  ↓
人类决定 merge / release
```

如果另一个系统已经拥有当前任务的 worker/session、workspace、PR/CI-review 或
release 生命周期，TheMasterplan 进入 `ABSTAINED`，不与外部工作流竞争治理权。
完整边界见
[docs/external-workflow-abstention.md](docs/external-workflow-abstention.md)。

## 快速采用

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
    uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.0.0
    with:
      policy-ref: v5.0.0
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

在已授权范围内，Agent 应持续工作直到：

1. 请求结果已经实现；
2. 与本次改动相关的验证通过；
3. 本次改动造成的失败已修复并复验；
4. 最终 diff 已审阅；
5. 或真正的人类决策边界出现。

安全的本地读取、编辑、格式化、lint、测试、修复本次改动造成的失败和重跑相关
验证，不需要逐步请求批准。

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

当前稳定 Release：**v5.0.0**。

普通 `/TheMasterplan` 任务不会自动检查更新。只有明确的 update、adopt、
maintenance 或版本检查意图才加载更新流程并执行只读检查。

版本通道：

- `v5.0.0`：当前稳定不可变 Release tag；
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

## 来源

TheMasterplan 整理自
[OasisSaber/agentic-project-workflow](https://github.com/OasisSaber/agentic-project-workflow)
的最终接受基线。历史研发记录保留在旧仓库。

基线提交：`ee0482d08ea6859bef2d1c06f37fa97bb25a575f`

## License

This project is licensed under the [MIT License](LICENSE).
