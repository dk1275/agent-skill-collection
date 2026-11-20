# manage-taskboard

让 Agent 通过 `taskctl` 管理 Codex Taskboard / e-taskboard 的项目、事项、评论和状态。它是一份**操作规范与命令参考**，不包含任务板服务、`taskctl` 程序或用户数据。

## 适合什么时候用

- 用户给出明确的任务板事项 ID，要求查看、执行、评论或更新状态。
- 用户要求把一项长期需求记录到任务板，或查询项目待办。
- 需要设置或检查 `taskctl` 的云端连接。

普通文档写作、项目代码编辑如果不涉及任务板事项，就不需要调用本技能。

## 依赖与安装

1. 先安装并配置你使用的 Taskboard 服务及 `taskctl`。本仓库没有提供它们的安装包。
2. 将本目录放到 Agent 可发现的技能目录。通用安装示例见[仓库首页](../../README.md#安装)。
3. 运行只读检查，确认命令与服务可用：

```bash
taskctl context current --json
taskctl project list --json
```

本地服务默认地址、可配置环境变量和云端连接方式见[CLI 参考](references/cli.md)。如果命令不存在或服务不可用，先修复依赖；安装 `SKILL.md` 本身不会启动服务。

## Agent 的基本工作顺序

1. 使用用户给出的原始事项 ID，不猜测或改写前缀。
2. 先读取事项和最新评论，判断任务是否获准开始。
3. 只有可认领的 `todo` 才按版本号移到 `in_progress`；`backlog`、被其他会话认领或明确要求等待的事项不能擅自开工。
4. 完成工作后验证结果、留下带有变更和风险说明的评论，再移到 `in_review`。
5. 只有用户明确验收或要求完成时，才移到 `done`。

这些并发和授权边界由[SKILL.md](SKILL.md)定义；具体参数参阅[CLI 参考](references/cli.md)。

## 写操作前要知道

- `taskctl` 的写操作需要当前 Codex 会话 ID；在其他环境中要显式提供 `--thread-id`。
- 更新事项须先读最新 `version`，再用 `--if-version` 写入，避免覆盖别人刚做的修改。
- 云端模式通过本机 companion（本地配套服务）连接上游；不要把普通 Taskboard HTTP API 误称为 companion API。
- 评论、状态变化和建单会改变真实任务板数据。先确认项目和事项，再写入。

## 文件

- [SKILL.md](SKILL.md)：Agent 的行为规则。
- [references/cli.md](references/cli.md)：`taskctl` 命令、参数和输出约定。
- `agents/openai.yaml`：供支持该格式的 Agent 读取的技能元数据。
