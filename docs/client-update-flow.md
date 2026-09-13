# 客户项目更新检测与升级流程（v5.0.0）

> 面向采用项目说明 TheMasterplan 的更新检测行为与升级确认门。检测逻辑的
> 权威实现是 `skills/themasterplan/scripts/tmlib/update_check.py` 与
> `themasterplan.py check-update`；本文件只解释使用方式，不复制实现。

## v5：意图驱动的更新检测

v5 不再在每次 `/TheMasterplan` 或 `/themasterplan` 调用时自动检查更新。

普通实现、修复、文档、测试和 PR 任务：

```text
不自动 check-update
```

只有当用户或当前任务明确进入以下路径时，才读取本文件并运行更新检测：

```text
adopt
update
upgrade
maintenance / version check
```

采用项目存在 `.themasterplan/state.json` 与
`.themasterplan/bin/themasterplan.py` 时，可只读运行：

```bash
python .themasterplan/bin/themasterplan.py check-update --root . --json
```

检测只比较当前采用版本与最新稳定 GitHub Release，不修改项目文件。可能状态：

| 状态 | 含义 | 行为 |
|---|---|---|
| `CURRENT` | 当前版本等于最新稳定版本 | 报告后结束更新检查 |
| `UPDATE_AVAILABLE` | 存在更高稳定版本 | 报告版本与提交身份，由用户决定是否生成计划 |
| `AHEAD` | 当前版本高于最新稳定 Release | 如实报告 |
| `UNKNOWN` | 当前来源无法与稳定 Release 比较 | 如实报告 |
| `UNAVAILABLE` | 网络或远端查询失败 | 只提示，不阻断其他任务 |
| `NOT_ADOPTED` | 无有效 `.themasterplan/state.json` | 报告未采用 |

`check-update` 忽略 Draft、Prerelease（除非 `--include-prerelease`）、浮动
`main`、未发布 Tag 与非 SemVer Tag；Release Tag 会解析为完整提交 SHA。

## 确认门

更新路径分为三个阶段：

1. **检测**：`check-update` 只读，可在明确的更新/维护意图下直接运行；
2. **计划**：只有用户明确要求查看/生成升级计划时才运行只读 `plan-update`；
3. **应用**：展示完整计划后，只有用户明确批准该计划，才运行 `apply-update`。

计划必须展示 `UPDATE_SAFE` / `ADD` / `UNCHANGED` /
`REMOVED_UPSTREAM` / `LOCAL_MODIFIED` 与 `stop_conditions`。TheMasterplan 不自动
升级，也不自动创建升级 PR。

项目自有接口，例如 `.github/workflows/check.yml`、`scripts/check.sh` 与
`.opencode/`，仍按各自所有权处理；generated-if-missing / project-owned 文件不会
因为版本升级被静默覆盖。

## check-update 命令

```text
check-update
  --root <project-root>                默认 .
  --repository <owner/repo>            默认从 .themasterplan/state.json 读取
  --include-prerelease                 默认 false
  --no-cache                           默认 false
  --json                               输出 JSON（当前默认即 JSON）
```

输出示例：

```json
{
  "schema_version": 1,
  "status": "UPDATE_AVAILABLE",
  "current": {
    "repository": "OasisSaber/TheMasterplan",
    "version": "v4.1.0",
    "commit": "<full-sha>"
  },
  "latest": {
    "version": "v5.0.0",
    "commit": "<full-sha>",
    "release_url": "<url>",
    "published_at": "<timestamp>"
  },
  "recommended_next_step": "ask-user",
  "writes_performed": false
}
```

退出码：`0` = 检测完成（含 `CURRENT`/`UPDATE_AVAILABLE`/`AHEAD`/`UNKNOWN`/
`NOT_ADOPTED`）；`1` = 本地状态损坏；`2` = 参数或执行器错误；`3` = 远端
不可用。

## plan-update 与 apply-update

```bash
python .themasterplan/bin/themasterplan.py plan-update \
  --root . \
  --source <target-version> \
  --commit <target-full-sha> \
  --repository OasisSaber/TheMasterplan \
  --output .themasterplan/update-<target-version>.json
```

```bash
python .themasterplan/bin/themasterplan.py apply-update \
  --root . \
  --plan .themasterplan/update-<target-version>.json \
  --source <target-version> \
  --commit <target-full-sha> \
  --repository OasisSaber/TheMasterplan
```

`plan-update` 只读；`apply-update` 要求显式来源身份（版本 + 完整 SHA +
repository）。被本地修改的受管文件不会被覆盖；上游删除的文件仅在本地内容与
记录 hash 一致时删除。

## v4.x → v5 Adapter 迁移

v5 删除 Adapter 抽象：

```text
components.adapters
selection.adapter
adapters/generic.md
--adapter
detected_adapter
```

v4.x 的标准采用状态：

```json
"adapter": "generic"
```

被视为已知的历史 no-op。升级到 v5 时：

- `plan-update` 接受该值；
- 输出的 v5 `selection` 删除 `adapter`；
- 未修改的受管 `adapters/generic.md` 作为 `REMOVED_UPSTREAM` 安全移除；
- 若本地 `adapters/generic.md` 已修改，则 `LOCAL_MODIFIED` / `stop_conditions`
  阻止自动删除；
- 除 `generic` 外的未知历史 Adapter 值 fail closed，不静默解释成 v5 行为。

因此 Adapter 删除是可审阅迁移，不是无条件删文件。

## Actions 手动同步

升级不会自动覆盖业务仓库已有的 GitHub Actions。采用者需要把当前版调用同步为：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@<target-version>
with:
  policy-ref: <target-version>
```

将 `<target-version>` 替换为明确选择的稳定 Release tag，例如 `v5.0.0`。

`uses` ref 与 `policy-ref` 必须一致；v1 冻结兼容线是独立接口：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/aw-check.yml@v1
```

不得把当前版路径与 `policy-ref: v1` 混用。

## OpenCode

`.opencode/skills/themasterplan/SKILL.md` 与
`.opencode/commands/themasterplan.md` 是极薄入口，不再复制更新状态机。

普通 OpenCode 任务不会自动更新检测。只有进入本文件描述的 update/adopt 路径时
才调用更新 executor。

外部交付工作流已经拥有当前任务生命周期时，TheMasterplan `ABSTAINED`；这与
版本检测是两个独立概念。

## 回滚

- 代码回滚：使用 `git revert`，或从上一已知正常 Release 重新生成升级计划；
- Actions 回滚：`uses` 与 `policy-ref` 同步回退到上一版本；
- 已发布 Tag 不删除、不移动、不重写；修复使用新的前向版本。

## 离线与缓存

无网络、GitHub API 不可用或 rate limit 时，`check-update` 返回 `UNAVAILABLE`
并附带原因。普通任务本来就不依赖更新检测，因此不受影响。

检测结果可缓存到 `.themasterplan/cache/update-check.json`（默认 6 小时 TTL，
不随 Git 提交，不包含 Token）。`--no-cache` 强制实时查询；缓存损坏时忽略并
重新查询；缓存写入失败不影响检测结果。

## 不自动升级声明

TheMasterplan 不会自动：

- 在普通任务中运行 `check-update`；
- 运行 `plan-update`；
- 运行 `apply-update`；
- 覆盖项目自有 `uses` / `policy-ref` / `scripts/check.sh` / `.opencode/`；
- 创建升级 PR；
- merge、release 或 deploy。
