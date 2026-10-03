# 客户项目更新检测与升级流程（v5.0.0）

> 面向采用项目说明 TheMasterplan 的更新检测行为与升级确认门。检测逻辑的
> 权威实现是 `skills/themasterplan/scripts/tmlib/update_check.py` 与
> `themasterplan.py check-update`；本文件只解释使用方式，不复制实现。

## 更新检测行为

v5 将更新检测从普通 Skill 调用的默认 side task 改为**明确意图触发**。只有用户
提出 update、adopt、maintenance、版本检查等相关请求时，才加载本文件并运行：

```bash
python .themasterplan/bin/themasterplan.py check-update --root . --json
```

`check-update` 只比较“当前采用版本”与“最新稳定 GitHub Release”，不修改受管
规则、业务代码或采用状态；可写入可丢弃的本地缓存（见缓存说明）。可能的状态：

| 状态 | 含义 | 命令后的处理 |
|---|---|---|
| `CURRENT` | 当前版本等于最新稳定版本 | 报告结果 |
| `UPDATE_AVAILABLE` | 存在更高稳定版本 | 报告版本与提交身份；已有升级/生成计划意图则准备计划，仅查版本则报告 |
| `AHEAD` | 当前版本高于最新稳定 Release | 报告结果 |
| `UNKNOWN` | 当前来源无法与稳定 Release 比较 | 报告结果 |
| `UNAVAILABLE` | 网络或远端查询失败 | 如实报告，不影响无关任务 |
| `NOT_ADOPTED` | 无有效 `.themasterplan/state.json` | 报告未采用 |

`check-update` 忽略 Draft、Prerelease（除非 `--include-prerelease`）、浮动
`main`、未发布 Tag 与非 SemVer Tag；Release Tag 会解析为完整提交 SHA。

## 用户确认门：准备与应用

检测、计划和应用是不同阶段，但不要求每阶段重复确认：

1. **自主准备**：明确的升级或生成计划请求已覆盖检测、固定来源身份与
   `plan-update`；不再询问是否生成计划。仅查版本的请求不扩展成升级计划，
   普通任务也不触发更新维护。计划不应用变更，但 `--output` 会写本地计划文件。
2. **显式应用批准**：展示完整计划（`UPDATE_SAFE`/`ADD`/`UNCHANGED`/
   `REMOVED_UPSTREAM`/`LOCAL_MODIFIED`/`stop_conditions`）、来源版本、完整
   SHA、repository、影响与 diff 后，请求人类批准精确计划。批准前不得运行
   `apply-update`；泛泛的“更新一下”不替代这道应用门。
3. **项目接口范围**：`.github/workflows/check.yml`、`scripts/check.sh`、
   `.opencode/` 不在受管清单内。如需修改，列入同一审核的范围和 diff，可由
   一次聚合授权覆盖；未列入则不修改，需要时取得新增范围授权。

按 [Core Policy](../core/policy.md) 的授权语义执行：已批准范围内不重复询问；
来源身份、计划内容、本地 hash 或目标状态变化时停止，重新准备并审核。

TheMasterplan 不会自动升级，也不会自动修改 `uses`、`policy-ref` 或自动
创建升级 PR。

## check-update 命令

```text
check-update
  --root <project-root>                默认 .
  --repository <owner/repo>            默认从 .themasterplan/state.json 读取
  --include-prerelease                 默认 false
  --no-cache                           默认 false（强制实时查询）
  --json                               输出机器可读 JSON（默认即 JSON）
```

输出示例（`UPDATE_AVAILABLE`）：

```json
{
  "schema_version": 1,
  "status": "UPDATE_AVAILABLE",
  "current": {
    "repository": "OasisSaber/TheMasterplan",
    "version": "v3.1.0",
    "commit": "<full-sha>"
  },
  "latest": {
    "version": "v3.1.1",
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
不可用（Skill 只提示，不阻断任务）。

`writes_performed: false` 指没有应用治理或业务变更，不包含可丢弃的检测缓存。

## plan-update 与 apply-update

升级流程复用既有命令：

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

`plan-update` 不修改受管文件，指定输出时写本地计划；`apply-update` 要求显式来源身份（版本 + 完整 SHA +
repository）。被本地修改的文件不会被覆盖（`LOCAL_MODIFIED` 停止）；上游
删除的文件仅在本地与记录 hash 一致时删除。

## Actions 手动同步

升级执行器不会修改业务仓库的 GitHub Actions。采用者或获明确批准的 Agent
按审核范围同步：

```yaml
uses: OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@<target-version>
with:
  policy-ref: <target-version>
```

将 `<target-version>` 替换为本次明确选择的稳定 Release tag
（例如 `v4.0.0`）。

`uses` 引用版本与 `policy-ref` **必须同时更新且一致**；禁止混合版本
（如 `@v4.0.0` + `policy-ref: v1`）。

## OpenCode 入口同步与外部工作流退让

`.opencode/` 下的 Skill 与命令由项目显式复制维护，不在受管清单内：

```text
.opencode/skills/themasterplan/SKILL.md
.opencode/commands/themasterplan.md
```

v5 删除当前 CLI/state/Harness 中的 Adapter 抽象。新采用不再写入
`selection.adapter`，也没有 `--adapter` 参数或 `adapters/generic.md`。

为保证已发布 v4.1.x 客户能够由**旧执行器**规划主版本升级，v5 分发 Manifest
暂时保留机器级 `components.adapters=["generic"]` 兼容桥；v5 执行器忽略它，
它不是 Agent Context surface。

v4 state 中的 `adapter=generic` 是已知历史 no-op：v5 执行器在下一次写回 state
时将其规范化移除。任何其他历史 Adapter 值继续 fail closed，不得静默解释为
generic。若当前任务已由外部交付工作流拥有，则按治理所有权规则
`ABSTAINED`，不运行升级事务。

## 回滚

- 代码回滚：`git revert` 或恢复到上一已知正常的 TheMasterplan tag 的
  受管文件（`apply-update` 的 `UNCHANGED`/`UPDATE_SAFE` 分类可先审阅）；
- Actions 回滚：`uses` 与 `policy-ref` 同步回退到上一版本；
- 已发布的 tag 不删除、不移动、不重写；上游修复发布新补丁版本。

## 离线行为

无网络、GitHub API 不可用或 rate limit 时，`check-update` 返回
`UNAVAILABLE` 并附带原因；Skill 只提示一次，不阻断当前任务。采用项目
可以完全离线使用已安装版本。

## 缓存说明

检测结果可缓存到 `.themasterplan/cache/update-check.json`（默认 6 小时 TTL，不随
Git 提交，不包含 Token）。`--no-cache` 强制实时查询；缓存损坏时忽略并
重新查询；缓存写入失败不影响检测结果。缓存不是功能依赖，删除无影响。

## 不自动升级声明

TheMasterplan 不会把检查或准备当成应用授权：

- 普通任务不运行更新检测或计划；仅查版本不隐式生成升级计划；
- 有明确升级/计划意图时可自主运行 `plan-update`，不逐步请求批准；
- 未经精确计划批准不运行 `apply-update`；`LOCAL_MODIFIED` 与停止条件不绕过；
- 未列入批准范围不修改 `uses` / `policy-ref` / `scripts/check.sh` / `.opencode/`；
- 未获相应授权不创建升级 PR、merge、release 或 deploy。

准备可以连续执行；真正应用、范围扩大与外部交付仍有明确授权门。
