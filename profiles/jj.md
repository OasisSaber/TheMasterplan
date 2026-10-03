# jj Profile：发布事务确认与验证

> 本文件是 [Core Policy](../core/policy.md) 的 Jujutsu profile：jj 解析候选
> change，Git transport 创建 annotated tag 和推送，gh 创建 Release。
> 采用项目只需本 Profile 与已安装的 Core，不依赖另一个 Profile 或上游文档。
> Git transport 必须能访问当前 jj 仓库的 Git 元数据；不可用时停止并报告限制，
> 不为发布擅自初始化或转换仓库。

## 发布约束

- 候选 change 解析为完整 Git commit SHA，且等于最新 `origin/main`。
- 顺序：创建并 push tag → 固定 tag 消费者 smoke test → 创建 Release → 远端验证。
- `v1` 兼容线冻结：不推进稳定 bookmark，不执行 @v1 smoke，不要求 v1 与候选对齐。
- 授权、失效条件、部分失败恢复和最终审核要素以 `core/policy.md` 为准。
  人类批准精确完整事务后连续执行；不得逐步重复确认，也不得盲目重试。

## 阶段 A：自主准备

只读检查、候选解析、验证和审核材料准备不需要逐步批准。

```bash
jj git fetch --remote origin
jj --no-pager log -r <candidate-change> --no-graph -T 'commit_id'
git ls-remote origin "refs/heads/main"
git ls-remote --tags origin
jj tag list
```

固定候选为 `APPROVED_CANDIDATE_SHA`；审核中不得用 `@`、`main` 或 change ID
前缀代替完整 SHA。审核列明 `TAG`、`NOTES_FILE`、完整写操作、顺序、验证结果、
当前远端状态和停止条件。目标 tag 在本地和远端都必须不存在；通过 gh 核实
目标 Release 不存在。网络、认证或查询失败不是“不存在”的证据，应停止核实。

## 阶段 C：执行已批准事务

仅在人类批准后执行。写入前重新核验 SHA、tag 与 Release 未变化；任何差异或
检查失败均按 Policy 停止重新审核。下列命令不是免除这些检查的快捷通道。

```bash
set -euo pipefail
APPROVED_CANDIDATE_SHA="${APPROVED_CANDIDATE_SHA:?set the approved full commit SHA}"
TAG="${TAG:?set the approved release tag}"
NOTES_FILE="${NOTES_FILE:?set the approved notes file}"
git check-ref-format "refs/tags/$TAG"
git fetch origin
CUR_MAIN=$(git ls-remote origin "refs/heads/main" | awk '{print $1}')
[ -n "$CUR_MAIN" ] && [ "$CUR_MAIN" = "$APPROVED_CANDIDATE_SHA" ] || exit 1
REMOTE_TAG=$(git ls-remote --tags origin "refs/tags/$TAG")
LOCAL_TAG=$(git tag --list "$TAG")
[ -z "$REMOTE_TAG" ] && [ -z "$LOCAL_TAG" ] || exit 1
# Release 不存在的检查也必须在写入前重新完成，查询失败时停止。
git tag -a "$TAG" -m "Release $TAG" "$APPROVED_CANDIDATE_SHA"
git push origin "$TAG"
```

现在运行审核中列明的**固定 tag 消费者 smoke test**并检查退出码与结果。
没有实际成功证据（仅有注释、计划或构造命令不算通过）时，不得运行以下命令：

```bash
gh release create "$TAG" --verify-tag --title "$TAG" --notes-file "$NOTES_FILE"
```

不使用 `jj tag set` 替代上述 annotated tag 创建：它会移动已有 tag，也不满足
本发布路径的 annotated tag 契约。已批准操作部分成功时先核验远端状态，不猜测、
不自动删除残留 tag、不用强推恢复。

## 阶段 D：发布后验证

```bash
set -euo pipefail
jj git fetch --remote origin
TAG_COMMIT=$(git ls-remote --tags origin "refs/tags/$TAG^{}" | awk '{print $1}')
[ "$TAG_COMMIT" = "$APPROVED_CANDIDATE_SHA" ] || exit 1
gh release view "$TAG" --json tagName,isDraft,isPrerelease
jj --no-pager log -r "$APPROVED_CANDIDATE_SHA" --no-graph -T 'commit_id'
```

核对 peeled SHA 等于候选、`tagName == TAG`、`isDraft == false`、Notes 正确，
无审核范围外 ref 或修改；`v1` 保持冻结。任何差异停止并重新审核。

## 禁止

- 用含糊 revision 或非最新 `origin/main` 的候选发布。
- 未批准就创建 tag、push 或创建 Release，或 smoke 未通过就创建 Release。
- 强推、覆盖/移动/删除已发布 tag、擅自推进稳定 bookmark。
- 跳过远端验证，或把查询失败、计划、注释当作成功证据。
- 违反 Core Policy 的授权失效与部分失败边界。
