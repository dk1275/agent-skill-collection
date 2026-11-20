# knowledge-base-sync｜知识库同步

在 macOS 上，用脚本把**你自己的**本地 Git 知识库与已配置的远端同步。公开版没有知识库内容、个人仓库地址或认证信息，也不会自动安装后台定时服务。

## 适合什么时候用

你已经有本地 Git 知识库，并已自行配置需要同步的远端，希望在执行前检查状态，或按需运行一次同步。这个技能针对脚本当前实现的 `main` 分支、`origin` 与 `gitee` 两个远端；如果你的仓库结构不同，先修改脚本并验证，不要直接运行。

## 运行前必须完成

1. 查看[脚本](scripts/kb-sync.sh)的 `REPO`、`REMOTE`、`BRANCH`、`STATE_DIR` 设置。默认的 `<your-knowledge-base>` 只是占位符。
2. 确认本地目录是正确的 Git 仓库，当前分支为 `main`，`origin` 和 `gitee` 都指向**你自己的**预期远端。
3. 确认 Git 身份验证已配置，仓库中没有不应上传的文件或秘密。脚本会对所有未提交改动运行 `git add -A` 并创建提交。
4. 首次运行前自行保留必要的恢复依据，例如检查当前提交号和 `git status`。不要在含未审查资料的仓库上试跑。

可先在终端检查：

```bash
git -C /path/to/your-knowledge-base status --short --branch
git -C /path/to/your-knowledge-base remote -v
```

## 运行方式

在仓库根目录指定真实知识库路径后，手动运行一次：

```bash
KB_SYNC_REPO=/path/to/your-knowledge-base \
  bash skills/knowledge-base-sync/scripts/kb-sync.sh --once
```

也支持 `--status` 和持续运行的 `--loop`。**先确认一次运行成功，再考虑持续运行。** 脚本会把输出写入 `~/Library/Application Support/knowledge-base-sync/sync.log`，因此终端里没有输出不代表成功；检查退出码和日志。技能本身不创建 macOS LaunchAgent。

## 脚本会做什么

- 检查当前分支及是否存在未完成的合并或变基。
- 等待短暂防抖后，提交本地未提交改动。
- 从 `origin/main` 与 `gitee/main` 获取并合并更新，再推送到两个远端。
- 遇到冲突或远端失败时停止本轮同步，并在日志中记录情况；不会强推或重置仓库。

**注意：** `--loop` 会定期重试普通失败。遇到合并冲突时不要继续让它自动运行；先停下进程，人工处理仓库状态，再执行一次 `--once` 验证。此脚本面向已经理解 Git 同步后果的用户。

## 文件

- [SKILL.md](SKILL.md)：Agent 使用边界。
- [scripts/kb-sync.sh](scripts/kb-sync.sh)：实际执行同步的脚本。
