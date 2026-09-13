# Validation

`scripts/check.sh` 是本仓库本地与 CI 共用的权威验证入口。它执行：

1. 受跟踪 Python 脚本语法检查；
2. `scripts/test_*.py` 单元/临时仓库集成测试；
3. `scripts/validate.sh` 的 Markdown 链接、Shell 提交模式、YAML 与 Shell 语法检查。

运行环境需要 Bash、Git、Python 和 PyYAML。持续集成当前使用固定 Python/PyYAML 环境；本地按 `scripts/requirements.txt` 安装验证依赖。

```bash
python -m pip install --disable-pip-version-check -r scripts/requirements.txt
bash scripts/check.sh
```

PowerShell 7 入口不复制验证规则，而是委托同一 Bash 权威入口：

```powershell
pwsh -NoProfile -File scripts/check.ps1
```

Windows 优先使用 Git for Windows 自带 Bash；其他平台从 `PATH` 定位 `bash`。

## v5 Context-Minimal 契约

`scripts/test_context_minimal_contract.py` 机械验证：

- Manifest 为 v5 且没有 Adapter component/file；
- `plan-adopt` 不再暴露 `--adapter`；
- `inspect` 不再暴露 `detected_adapter`；
- `AGENTS.md` 是 Context Router，包含 Completion Contract，不再有全栈加载顺序；
- canonical Skill、OpenCode Skill/Command 保持极薄，不复制 update/PR 机械契约；
- `core/workflow.md` 是 ABSTAINED、默认继续与真实停止边界的权威来源。

`scripts/test_v5_adapter_migration.py` 验证 v4.x → v5 的 breaking-schema 迁移：

- 历史 `adapter=generic` 被规范化移除；
- 未修改的受管 `adapters/generic.md` 安全按 `REMOVED_UPSTREAM` 删除；
- 本地修改过的旧 Adapter 文件 fail closed，不被覆盖/删除；
- 未知历史 Adapter selection fail closed。

这些测试验证机械边界，不把整套规则重新复制进 Prompt。

## 消费者契约

`scripts/validate_consumer.py` 机械验证中央 Actions 调用方的最小契约：根部 `AGENTS.md` 存在，`project-check-path` 是安全 POSIX 相对路径、受 Git 跟踪的普通文件且不是符号链接。

```bash
python scripts/validate_consumer.py <repository-root> <project-check-path>
```

完整接口定义见 [docs/actions-interface.md](../docs/actions-interface.md)。

## PR 正文契约

`scripts/validate_pr_body.py` 与 `.github/pull_request_template.md` 是 PR 正文机械契约的单一事实来源。v5 Skill/AGENTS 不再复制字段清单。

CI 仅在 Pull Request 事件中对实时正文运行 PR validator。

## Actions 契约

`scripts/test_actions_contract.py` 验证 `.github/workflows/themasterplan-check.yml` 的 `workflow_call`、稳定 Job 名称、只读权限、无 `pull_request_target`/Secrets、第三方 Action 完整 SHA、默认输入、超时与 checkout 路径。

## 支持状态

- `VERIFIED`：当前 Ubuntu GitHub Actions 的 Bash 权威入口和 PowerShell 7 委托路径。
- `PARTIAL`：真实 Windows PowerShell 7 + Git for Windows 与 macOS Bash；采用项目应在目标平台运行 smoke。
- Windows PowerShell 5.1 不在支持范围。

入口存在不等于上游已经验证所有原生平台。
