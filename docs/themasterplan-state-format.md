# `.themasterplan` 状态目录与格式（v5）

`.themasterplan/state.json` 描述采用事实，不描述当前任务的临时治理状态。

## 目录

```text
.themasterplan/
├── state.json
├── bin/
└── cache/
```

## v5 state

```json
{
  "schema_version": 1,
  "source": {
    "repository": "OasisSaber/TheMasterplan",
    "version": "v5.0.0",
    "commit": "<full-sha>"
  },
  "selection": {
    "profile": "git",
    "validation_path": "scripts/check.sh",
    "default_branch": "main"
  },
  "managed_files": {},
  "adoption": {
    "date": "YYYY-MM-DD",
    "platform": "<os>",
    "git_version": "<version>",
    "jj_version": "<version-or-null>",
    "status": "PARTIAL"
  }
}
```

## v5 变化

v5 删除 Adapter 抽象：

```text
selection.adapter
components.adapters
adapters/generic.md
--adapter CLI 参数
detected_adapter
```

都不再属于当前 schema / CLI surface。

从 v4.x 更新时，旧 state 中：

```json
"adapter": "generic"
```

被视为可迁移的历史字段。`plan-update` 应接受它，并在生成 v5 update plan 时将
其从 `selection` 中移除。除 `generic` 外的历史 Adapter 值继续 fail closed，不得
静默迁移。

## 临时任务状态

`ACTIVE` / `ABSTAINED` 是当前任务的上下文决策，不写入 state。

## 所有权

- `managed-replace`：TheMasterplan 管理完整文件；
- `managed-block`：只管理标记区块；
- `generated-if-missing`：仅缺失时生成；
- `project-owned`：永不自动覆盖。

## 安全

- state 不保存 Token/Secret/私人数据；
- 路径必须留在仓库根目录内；
- manifest 目标不得重复；
- 生产来源 commit 使用完整 SHA。
