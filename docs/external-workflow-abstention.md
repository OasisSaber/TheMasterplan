# 外部交付工作流共存与自动退让

> 本文件只在当前任务出现外部治理所有权问题时按 Context Router 读取。

## 目标

TheMasterplan 是轻量的单一交付治理协议，不是外部编排器兼容层。

同一任务只有两种运行状态：

```text
ACTIVE
ABSTAINED
```

- `ACTIVE`：TheMasterplan 是当前任务的交付治理所有者。
- `ABSTAINED`：另一个系统已经拥有当前任务的交付生命周期，TheMasterplan 主动退让。

`ABSTAINED` 是任务级瞬时状态，不写入 `.themasterplan/state.json`，也不增加状态 schema。

## 什么不构成冲突

单纯使用以下工具不意味着外部治理接管：

- 编辑器、Shell；
- Git / Jujutsu；
- OpenCode、Codex、ChatGPT 等直接执行 Harness；
- test、lint、build 工具。

它们只执行任务、没有拥有 worker/session/workspace/PR 生命周期时，TheMasterplan 保持 `ACTIVE`。

## 什么构成外部治理所有权

存在明确证据表明另一个系统拥有当前任务的一个或多个生命周期环节时，TheMasterplan `ABSTAINED`：

- 管理 worker / session；
- 创建、复用或回收 task workspace / worktree / branch；
- 拥有 Issue/任务 → PR 状态机；
- 把 CI failure、review、merge conflict 路由给特定 worker；
- 管理 merge、release 或 deploy 生命周期；
- 明确声明自己的交付规则为当前任务治理来源。

判断基于“谁拥有生命周期”，不是工具品牌。不要维护 Agent Orchestrator、Trellis 或其他工具的版本/配置特征矩阵。

## ABSTAINED 行为

确认外部治理已接管后：

1. 报告 `TheMasterplan: ABSTAINED — external delivery workflow owns this task.`；
2. 不继续施加 TheMasterplan 的任务、PR、reaction、cleanup 或发布生命周期；
3. 不进入 adopt/update 路径，不运行 `check-update` / `plan-update` / `apply-update`；
4. 不生成外部工作流专用配置或兼容层；
5. 不修改外部系统的 session、worker、workspace、branch、PR 或 pipeline；
6. 把控制权留给现有治理所有者。

所有权不明确且即将产生写操作时，询问人类；不要靠品牌猜测。

## 仓库级 CI

`ABSTAINED` 不动态重写或禁用项目已经配置的 GitHub Actions。项目 CI 仍按仓库配置运行。

如果项目要完全迁移到另一个治理系统，由人类在独立迁移任务中明确选择唯一治理方案，而不是让 TheMasterplan 在任务运行时修改仓库设置。

## v5 与 Adapter

v5 已删除 Adapter 抽象：

```text
adapters/generic.md
components.adapters
selection.adapter
--adapter
detected_adapter
```

外部治理退让不再通过 Adapter selection 表达，而是由当前任务上下文直接判断。

从 v4.x 更新时，历史 `adapter=generic` 是可迁移的 no-op 字段并被移除；其他未知历史 Adapter 值继续 fail closed。迁移细节见 [client-update-flow.md](client-update-flow.md)。

## 不做的事情

TheMasterplan 不：

- 维护外部 orchestrator Adapter；
- 跟踪外部工具配置 schema；
- 配置 reaction / claim / worker reuse；
- 宣称某个外部编排器 VERIFIED / PARTIAL；
- 为外部工作流提供自动 merge/release/deploy 协调；
- 建立通用互操作状态机。

核心原则：

> 没有其他治理所有者时 TheMasterplan 工作；已有其他治理所有者时 TheMasterplan 主动退让。
