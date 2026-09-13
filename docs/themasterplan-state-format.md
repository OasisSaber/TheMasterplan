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

v5 删除运行时 Adapter 抽象：

```text
selection.adapter（新采用不再写入）
adapters/generic.md
--adapter CLI 参数
detected_adapter
```

`distribution/manifest.json` 可暂时保留 `components.adapters=["generic"]` 作为 **v4 旧执行器升级兼容桥**。v5 的 CLI、文件选择和新 state 都忽略该字段；它不是当前 Agent/Harness surface。

从 v4.x 更新时，旧 state 中：

```json
"adapter": "generic"
```

被视为可迁移的历史字段。**v5 执行器**的 `plan-update` 接受它，并在生成
下一份 v5 update plan 时从 `selection` 中移除。首次从 v4.1.x 升到 v5 时，
发起事务的是已安装的 v4 旧执行器，因此该旧字段可能在首次 apply 后暂时保留；
安装完成后的 v5 执行器会容忍这一历史字段，并在后续 state 写回时规范化移除。
除 `generic` 外的历史 Adapter 值继续 fail closed，不得静默迁移。

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
