# TheMasterplan Agent Workflow

> 本文件是仓库级 Context Router。只保留项目事实、长期有效的硬边界，以及
> “什么时候读什么”。不要在普通任务开始前预读整套规则。

## 项目事实

- 项目：TheMasterplan
- 定位：单一交付责任人的轻量 AI 辅助代码交付治理协议。
- 默认分支：`main`
- 权威验证入口：`bash scripts/check.sh`
- 当前稳定中央 Actions：`OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v4.1.0`
- v1 冻结兼容线：`OasisSaber/TheMasterplan/.github/workflows/aw-check.yml@v1`
- 合并策略：默认由人类决定 Squash Merge；微小修复快速通道仅按
  `core/workflow.md` 的明确条件使用。
- 发布：tag-only；已发布 Tag 不移动、不覆盖；`v1` 不推进。

## 始终有效的边界

- 不提交 Secret、Token、明显私人数据、本机绝对路径、缓存或无关生成物。
- 不 force push，不覆盖或移动已发布 Tag，不猜测有冲突的远端 ref。
- 当前任务若已由另一个交付工作流拥有生命周期，按
  `core/workflow.md` 的治理所有权规则 `ABSTAINED`，不竞争控制权。
- merge、release、部署、受保护分支推进、破坏性远端操作，以及实质范围扩大，
  只有在对应授权存在时执行；具体授权语义按需读取 `core/policy.md`。
- 当前 Issue 或人类授权定义任务目标与范围，但不能覆盖安全、隐私、合规、
  平台权限或受保护分支限制。

## Context Router

只加载与当前任务有关的材料：

| 当前任务需要 | 读取 |
| --- | --- |
| 普通实现、修复、文档、测试、PR 交付 | `core/workflow.md` |
| merge / release / deploy / 远端删除 / 已发布历史重写 | `core/policy.md` |
| Git 发布或 Tag 操作 | `profiles/git.md` |
| Jujutsu 发布或 Tag 操作 | `profiles/jj.md` |
| Jujutsu 日常 change/bookmark 命令 | `skills/themasterplan/references/jj-lifecycle.md` |
| adoption / update / check-update | `docs/client-update-flow.md` |
| GitHub Actions 公共接口 | `docs/actions-interface.md` |
| 版本通道与 Release | `docs/release-channels.md` |
| 外部工作流所有权边界 | `docs/external-workflow-abstention.md` |
| 新项目采用与 smoke | `docs/adoption-guide.md` |

不要因为文件存在就读取它；按任务需要渐进披露。

## Completion Contract

在已授权范围内持续执行，直到：

1. 用户请求的结果已经实现；
2. 与本次改动相关的验证通过；
3. 本次改动造成的失败已修复并复验；
4. 最终 diff 已审阅；
5. 或出现真正需要人类决定的边界。

安全的本地读取、编辑、格式化、lint、测试、修复本次改动造成的失败和重跑相关
验证默认继续，不为这些步骤逐次请求批准。

## 权威顺序

系统/平台安全与权限 > 项目安全与受保护分支限制 > 本文件及其按需引用的 Core
规则 > 当前 Issue/明确授权 > 项目资料 > README/CONTRIBUTING 等辅助文档。
