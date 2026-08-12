# 外部交付工作流共存与自动退让

## 目标

TheMasterplan 是轻量的单一交付治理协议，不是外部编排器兼容层。

同一任务只有两种运行状态：

```text
ACTIVE
ABSTAINED
```

- `ACTIVE`：TheMasterplan 是当前任务唯一的交付治理工作流。
- `ABSTAINED`：已经有另一个系统拥有当前任务的交付生命周期，TheMasterplan
  主动退让，不再施加自己的任务生命周期规则。

`ABSTAINED` 是任务级、瞬时状态，不写入 `.aw/state.json`，也不增加新的状态
schema。

## 什么不构成冲突

单纯使用以下工具不意味着外部治理接管：

- 编辑器；
- Shell；
- Git / Jujutsu；
- 直接使用的 LLM Harness，例如 OpenCode、Codex、ChatGPT；
- 测试、lint、构建工具。

这些工具只执行当前任务，不自行拥有 worker/session/worktree/PR 生命周期时，
TheMasterplan 可以保持 `ACTIVE`。

## 什么构成外部治理所有权

存在明确证据表明另一个系统正在拥有当前任务的一个或多个生命周期环节时，
TheMasterplan 必须 `ABSTAINED`：

- 为任务分配或管理 worker / session；
- 自动创建、复用或回收 task workspace / worktree / branch；
- 拥有 Issue/任务 → PR 的状态机；
- 自动把 CI failure、review、merge conflict 路由给特定 worker；
- 管理 merge、release 或 deploy 的工作流；
- 明确声明自己的交付规则为当前任务的治理来源。

判断基于“谁拥有生命周期”，而不是品牌名。不得为了识别外部系统维护
Agent Orchestrator、Trellis 或其他工具的版本/配置特征矩阵。

## ABSTAINED 行为

一旦确认外部治理已经接管当前任务：

1. 报告：
   `TheMasterplan: ABSTAINED — external delivery workflow owns this task.`
2. 不继续套用 TheMasterplan 的任务 change、PR、reaction、cleanup 或发布规则。
3. 不运行 `check-update`、`plan-update`、`apply-update`。
4. 不为外部工作流生成配置、Adapter 或兼容层。
5. 不修改外部系统的 session、worker、worktree、branch、PR 或 pipeline。
6. 把控制权留给已经拥有生命周期的系统。

如果所有权不明确，在任何写操作前询问人类；不得靠品牌猜测。

## 仓库级 CI 说明

`ABSTAINED` 不会动态重写或禁用项目已经配置的 GitHub Actions。自动修改 CI
会引入额外状态、权限和兼容逻辑，与轻量化目标冲突。

因此：

- 任务级 Agent 治理可以 `ABSTAINED`；
- 项目已经显式配置的 CI 仍按项目配置运行；
- 若项目希望完全由另一个治理系统接管，应由人类在采用/迁移任务中明确选择
  唯一治理方案，而不是让 TheMasterplan 自动修改仓库设置。

## v3.1.1 → v3.2.0

v3.2.0 删除专用的 Agent Orchestrator 与 Trellis Adapter。

使用 `adapter=generic` 的采用项目可以走正常升级。

历史 `.aw/state.json` 若选择：

```text
adapter = trellis
adapter = agent-orchestrator
```

升级计划应 fail closed 为 `SELECTION_CHANGED` / `selection no longer supported`，
不得自动把选择改成 `generic`。

这不是升级器故障，而是有意的治理所有权迁移门。是否退出外部工作流并重新采用
`generic`，必须由人类单独决定。

## 不做的事情

TheMasterplan 不再：

- 维护外部 orchestrator Adapter；
- 跟踪外部工具配置 schema；
- 配置 reaction / claim / worker reuse；
- 宣称某个外部编排器 VERIFIED / PARTIAL；
- 为外部工作流提供自动 merge/release/deploy 协调；
- 建立通用互操作状态机。

核心原则：

> 没有其他治理系统时 TheMasterplan 工作；已有其他治理系统时 TheMasterplan
> 主动退让。
