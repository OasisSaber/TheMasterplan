# `.themasterplan` 状态目录与格式

> 本文档描述 `/TheMasterplan`（TheMasterplan 的简写；实际调用与文件命名一律使用
> 全称 `TheMasterplan`）接入后在采用项目生成的 `.themasterplan/` 目录结构与
> `.themasterplan/state.json` 格式。执行器实现见
> `skills/themasterplan/scripts/`（`themasterplan.py` + `tmlib/`）。

## 目录结构

```text
.themasterplan/
├── state.json   采用事实与更新锁定记录（必须受 Git 跟踪）
├── bin/         项目内锁定版本的执行器副本（themasterplan.py + tmlib/）
└── cache/       默认不提交；仅用于临时下载与计划生成（PR B 起使用）
```

## `state.json` 结构

```json
{
  "schema_version": 1,
  "source": {
    "repository": "OasisSaber/TheMasterplan",
    "version": "<distribution-version，如 v3.2.0>",
    "commit": "<full-sha>"
  },
  "selection": {
    "profile": "jj",
    "adapter": "generic",
    "validation_path": "scripts/check.sh",
    "default_branch": "main"
  },
  "managed_files": {
    "core/workflow.md": {
      "source": "core/workflow.md",
      "source_sha256": "<sha256>",
      "installed_sha256": "<sha256>",
      "ownership": "managed-replace"
    }
  },
  "adoption": {
    "date": "YYYY-MM-DD",
    "platform": "<os>",
    "git_version": "<version>",
    "jj_version": "<version-or-null>",
    "status": "PARTIAL"
  }
}
```

### 字段说明

- `source`：来源仓库、Release 版本与完整 commit SHA；`commit` 必须是
  40 位完整 SHA，不得使用不完整标识作为生产锁定值。
- `selection`：采用的 Profile、Adapter、项目验证入口与默认分支。
- `managed_files`：每个受管文件记录来源路径、来源 hash、安装后 hash 与
  所有权类型；hash 用于更新时检测本地修改。
- `adoption`：采用日期、平台与工具版本、生产状态（`READY` / `PARTIAL` /
  `BLOCKED`）。

### `.themasterplan/cache/update-check.json`

`check-update` 的可删除缓存（v3.1.1 起）：记录最近一次成功查询的
repository、最新稳定版本与提交 SHA、检查时间；默认 6 小时 TTL，不随 Git
提交，不含 Token。缓存损坏或过期时忽略并重新查询；写入失败不影响检测
结果；删除无影响。见 [client-update-flow.md](client-update-flow.md)。

## 文件所有权模型

| 类型 | 语义 |
|---|---|
| `managed-replace` | TheMasterplan 完全管理；当前 hash 与 `installed_sha256` 一致时可整体替换，否则标记 `MODIFIED` 停止 |
| `managed-block` | 只替换 `<!-- THEMASTERPLAN:BEGIN MANAGED -->` 与 `<!-- THEMASTERPLAN:END MANAGED -->` 之间的区块；区块外内容属于项目 |
| `generated-if-missing` | 只在缺失时生成模板；已存在默认不覆盖 |
| `project-owned` | 永不自动覆盖（项目文档、安全规范、部署配置、密钥等） |

## 安全要求

- 不在 `state.json` 中保存 Token、Secret、GitHub 凭据或用户隐私数据；
- 所有目标路径必须位于仓库根目录内（拒绝 `../`、绝对路径与符号链接写出）；
- manifest 不得声明重复目标；
- 下载内容（PR B）必须与 manifest 的 SHA-256 一致。
