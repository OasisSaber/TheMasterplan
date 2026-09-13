# 版本通道

TheMasterplan 中央 Actions 接口使用以下版本通道：

```text
main        TheMasterplan 开发与自测
v1          兼容线（冻结；工作流路径 aw-check.yml）
v5.0.0      当前版不可变 Release tag（工作流路径 themasterplan-check.yml）
v4.1.0      历史不可变 Release tag（工作流路径 themasterplan-check.yml）
v4.0.0      历史不可变 Release tag（工作流路径 themasterplan-check.yml）
完整 SHA    最高可复现性和候选/紧急固定
```

## 默认调用

v1 冻结兼容线：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/aw-check.yml@v1
```

当前版（推荐新采用，精确固定）：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.0.0
with:
  policy-ref: v5.0.0
```

## 严格固定

稳定 Release：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v5.0.0
with:
  policy-ref: v5.0.0
  project-check-path: scripts/check.sh
```

候选或调查场景可以把 `uses` 和 `policy-ref` 同时固定到同一个完整 commit SHA。

## 版本一致性

当前版固定调用必须满足：

```text
uses 引用版本 == policy-ref
```

不得把 `themasterplan-check.yml@<current-version>` 与 `policy-ref: v1` 混合。

v1 是独立冻结接口，继续使用 `aw-check.yml@v1`。

## 发布流程（tag-only）

发布采用单一最终授权门。授权语义见 `core/policy.md`，Git/Jujutsu 具体执行只在发布任务中按 Context Router 读取 `profiles/git.md` / `profiles/jj.md`。

```text
main 完成实现与验证
        ↓
独立消费者 smoke
        ↓
最终发布审核：版本、候选 SHA、tag、Release Notes、全部写操作与停止条件
        ↓
人类一次批准完整发布事务
        ↓
创建并 push annotated tag
        ↓
固定 tag consumer smoke
        ↓
创建 GitHub Release（--verify-tag）
        ↓
验证 Release 与 peeled tag SHA
        ↓
最终汇报
```

固定 Tag smoke 通过前不得创建 Release。发布授权后 Agent 在已列明且状态未变化的范围内连续执行，不逐步重复询问。

## v1 冻结规则

`v1` 不再推进：

- 不 force push；
- 不删除或移动；
- 不直接在 `v1` 开发；
- 不要求当前主版本与 v1 内容对齐；
- 已有消费者可继续使用 `aw-check.yml@v1`。

v5 Context-Minimal Reform 不改变 v1 的公共契约或冻结状态。

## 历史版本

`v4.1.0` 是 v5 的直接升级来源之一。v5 删除 Adapter 抽象并改变默认 Context 加载模型，但不重写或移动任何 v4 Tag / Release。

## 回退

```text
消费者临时固定上一正常 Release 或完整 SHA
        ↓
main 创建前向修复
        ↓
发布新的前向版本
```

不得通过强推、移动已发布 Tag 或改写 v1 回退历史。
