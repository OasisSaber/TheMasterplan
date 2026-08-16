# TheMasterplan Agent Workflow

> 本文件是本仓库唯一入口：定义加载顺序与分域权威，不复制规则正文。
> 规则分布：
> - 任务来源、工作区检查、验证真实性、diff 审阅、自审与交接：[core/workflow.md](core/workflow.md)
> - 权限与聚合授权、外部写操作边界、人类审批门、发布事务、安全停止条件：[core/policy.md](core/policy.md)
> - Git / jj 发布执行命令：[profiles/git.md](profiles/git.md)、[profiles/jj.md](profiles/jj.md)
> - Harness 边界：[adapters/generic.md](adapters/generic.md)；外部交付工作流介入时按 [docs/external-workflow-abstention.md](docs/external-workflow-abstention.md) 主动退让
> 各层通过链接引用，不复制同一规则。README、CONTRIBUTING、采用指南和其他
> 材料只能解释或辅助执行，不能覆盖本文件及其引用的规则。

## 项目事实

- 项目名：TheMasterplan
- 项目目标：维护面向个人开发者的“单一交付责任人的 AI 辅助代码交付治理协议”（任务生命周期 + 发布治理），并集中维护、版本化发布 GitHub Actions 可重用工作流接口；不承担外部 orchestrator 适配职责，治理所有权冲突时主动 `ABSTAINED`
- 中央 Actions 接口：`OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml`（v1 兼容线消费者引用 `aw-check.yml@v1`；当前版消费者引用 `themasterplan-check.yml@v4.0.0`），调用约束见 [docs/actions-interface.md](docs/actions-interface.md)，版本通道见 [docs/release-channels.md](docs/release-channels.md)
- 接口承诺：`v1` 生命周期内不得移动工作流路径、删除或重命名输入、更改默认项目验证入口、更改 required check 公共名称、新增 Secret 或写权限；中央接口变更视为公共 API 变更，破坏性调整只允许在下一主版本进行
- 默认分支：`main`
- 工具基线：Jujutsu `0.43.0` 的文档命令已验证；更高版本必须在采用时重新完成烟雾测试。Git `2.34.0` 或更高版本。
- 平台状态：`VERIFIED` 为 Ubuntu GitHub Actions 中的 Bash 入口和 PowerShell 委托入口；`PARTIAL` 为 macOS 与真实 Windows PowerShell 7 + Git for Windows 环境，采用时必须执行平台烟雾测试。
- 验证入口：
  ```bash
  bash scripts/check.sh
  ```
- 合并方式：只接受人类决定的 Squash Merge
- 版本通道状态：`v1` 兼容线已冻结（当前指向 v2.0.0 内容，不再推进）；`policy-ref` 默认值保持 `v1`；发布为 tag-only（创建 tag → 固定 tag smoke → Release，不推进 v1、不执行 @v1 smoke），流程见 [docs/release-channels.md](docs/release-channels.md) 与 [profiles/git.md](profiles/git.md)；未来版本通道调整作为独立发布任务处理
- merge、release、部署与受保护分支推进未经人类明确批准不得执行；人类一次批准完整发布事务（见 [core/policy.md](core/policy.md)）后，Agent 可在已列明范围内连续执行

采用到其他项目时，应更新本节中的项目目标、技术栈、验证命令和受保护分支。

## 权威顺序

1. 系统安全、法律与平台权限
2. 项目安全、隐私、合规和数据保护要求
3. 受保护分支、发布、部署和破坏性操作限制（授权语义见 [core/policy.md](core/policy.md)）
4. 根部 `AGENTS.md` 及其引用的 `core/` 规则
5. 当前 Issue 或明确人类授权
6. 项目架构、测试和交付资料
7. README、CONTRIBUTING、采用指南和其他辅助材料

当前 Issue 或明确人类授权只能定义任务目标、范围和验收条件，不能覆盖安全、隐私、合规、数据保护、受保护分支、发布、部署或破坏性操作限制。

## 加载顺序

开始工作前按以下顺序加载：

1. 根部 `AGENTS.md`（本文件）；
2. [core/workflow.md](core/workflow.md)（任务来源、工作区、验证、自审）；
3. [core/policy.md](core/policy.md)（授权与发布）；
4. 执行 [core/workflow.md](core/workflow.md) §0 治理所有权预检；若为
   `ABSTAINED`，报告后停止 TheMasterplan 工作流；
5. `ACTIVE` 时再加载项目采用的 [profiles/](profiles/git.md)（Git / jj 命令）
   与 [adapters/generic.md](adapters/generic.md)（薄 Harness 边界）；
6. 当前 Issue 或明确人类授权。

## 任务路径

复杂任务与小型低风险任务的路径、适用范围与授权记录要求见
[core/workflow.md](core/workflow.md) §1。无 Issue 时不得伪造编号；实现需要
扩大范围时必须停止，向人类说明原因并转为 Issue 路径。

## 验证与交付

工作区检查、任务 change 卫生、权威验证、完整 diff 审阅与 Agent 自审要求见
[core/workflow.md](core/workflow.md) §2-§6。每次 push 前必须运行权威验证
入口：

```bash
bash scripts/check.sh
```

PowerShell 7 等价入口委托上述权威命令，不维护第二套验证规则：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

验证失败时必须修正并重跑，不得把失败或未验证状态表述为成功。fetch 后发现
`main`、`main@origin` 或任务 bookmark 冲突时必须停止，不得猜测目标、自动
解决或 push。审查意见只使用三类表述：合并前必须修复、建议本次修复、可以
后续处理。

## 人工批准与聚合授权

人类保留最终决定权，不表示人类必须亲自操作。Agent 不得未经批准执行
merge、release、删除远端数据、破坏性操作或扩大范围；取得人类明确批准后，
Agent 可在批准范围内连续执行，不得把可由自身工具完成的操作转交人类手工
执行。

发布采用单一最终授权门，聚合授权的定义、审核要素、失效条件、部分失败处理
与术语对照见 [core/policy.md](core/policy.md)；Git 与 jj 下的安全执行方式
见 [profiles/git.md](profiles/git.md) 与 [profiles/jj.md](profiles/jj.md)。

Agent 不得把允许 push 或创建 Pull Request 解释为允许 merge 或 release。

## 安全与卫生

- 不提交密钥、访问令牌或明显的私人数据。
- 不提交本机绝对路径、缓存、临时文件或无关生成物。
- `main` 只接受经 Pull Request 的人类决定 Squash Merge。
- 发现当前操作违反已记录规则、权限或范围时，必须在产生外部影响前停止并请求人类修正或明确授权。
