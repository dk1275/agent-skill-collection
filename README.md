# Agent Skill Collection

一组供 Codex、WorkBuddy 等 Agent 按需使用的技能。这里的“常驻”是指技能文件安装在用户级目录，供后续任务发现和调用；**不是后台服务，也不是每次对话自动执行全部技能**。

本仓库收录 3 个技能的公开副本，并列出其他常用技能的原仓库。每个技能的具体操作规则以它自己的 `SKILL.md` 为准。公开副本不包含个人路径、私有仓库地址、密码或令牌。

## 全局常驻规则模板

[RESIDENT_RULES.md](RESIDENT_RULES.md) 是从作者本机全局规则整理出的**脱敏公开模板**，涵盖任务闭环、产品地图、验证、交接、技能管理和安全边界。原文件仍保留在作者本机，仓库副本与它不会自动同步。

使用前请按自己的 Agent、技能目录、知识库和部署授权调整。特别注意：模板中提到的文件、工具、技能和长期记忆目录并不随本仓库自动安装；**阅读模板也不等于授予 Agent 部署、发布或访问私人数据的权限**。

## 先看这里

| 技能 | 解决什么问题 | 使用前需要什么 | 入口 |
| --- | --- | --- | --- |
| `manage-taskboard` | 通过 `taskctl` 查询、认领、更新任务板事项 | 已安装 `taskctl`，且能连接相应任务板服务 | [SKILL.md](skills/manage-taskboard/SKILL.md) |
| `jingyan` | 从项目证据提取可复用方法，在新任务中注入，并用复盘闭环 | Python 3、自己指定的经验库目录 | [SKILL.md](skills/jingyan/SKILL.md) |
| `knowledge-base-sync` | 在 macOS 上同步自己的本地 Git 知识库与远端 | 已有 Git 仓库、正确配置的远端和 Git 凭据 | [SKILL.md](skills/knowledge-base-sync/SKILL.md) |

这些技能分别服务于任务跟踪、经验复用和知识库同步；互相独立，可只安装需要的一个。

## 安装

先把仓库克隆到自己选择的目录，再将所需技能目录复制或链接到 Agent 能读取的用户级技能目录。以下示例以 Codex 的 `~/.codex/skills` 为目标，假定该目录存在：

```bash
git clone https://github.com/dk1275/agent-skill-collection.git
mkdir -p ~/.codex/skills
ln -s "$(pwd)/agent-skill-collection/skills/jingyan" ~/.codex/skills/jingyan
```

如果 `~/.codex/skills/jingyan` 已存在，先检查它指向哪里，不要直接覆盖。WorkBuddy、DSH 或其他 Agent 的技能发现目录可能不同，应按各自环境设置；不要假设复制到一个目录就会被所有工具读取。安装后，打开目标目录下的 `SKILL.md`，确认路径及依赖，再在对话中明确调用相应技能。

## 技能说明

### manage-taskboard

在使用 Codex Taskboard 或 e-taskboard，并且已配置 `taskctl` 的环境中，用于管理任务、状态和评论。技能要求先读取事项及最新评论，按任务板的版本控制规则更新，避免重复建单或抢占别的会话正在处理的事项。

它**不自带任务板服务或 `taskctl` 程序**。仅复制技能文件不会创建任务板。先在本机确认 `taskctl` 可用，再参阅[命令参考](skills/manage-taskboard/references/cli.md)。

### jingyan

把已验证的项目经验整理成可复用方法。基本流程是：从项目证据提取候选经验；按经验库中的审批策略决定是否晋升；任务开始时注入适用的方法；任务结束时复盘并检查闭环。候选经验不会自动等同于已验证方法。

运行前选择一个自己的经验库目录，并在命令中传给 `--root`，例如：

```bash
python3 skills/jingyan/scripts/experience_tool.py --root /path/to/experience-library status
python3 skills/jingyan/scripts/experience_tool.py --root /path/to/experience-library policy show
```

首次使用先阅读[完整规则和命令](skills/jingyan/SKILL.md)，尤其是审批策略。不要把含密钥、客户个人信息或未经核实的结论写入共享经验库。

### knowledge-base-sync

适合已经拥有**自己的**本地 Git 知识库，并希望在 macOS 上同步到自己配置的远端的人。这个技能的公开副本将原机器的路径和远端改为占位符。它不包含知识库内容，也不会替你创建远端或配置身份验证。

使用前必须在[同步脚本](skills/knowledge-base-sync/scripts/kb-sync.sh)中配置知识库位置，并检查远端名称与分支是否符合你的仓库；`SKILL.md` 中的 `<...>` 也是待替换的说明文字。先手动运行 `--status`、`--once` 并确认结果，再考虑自行设置定时运行。**仅阅读或安装本仓库不会启动同步服务。**

脚本可能提交并推送知识库中的本地改动。首次运行前先检查 `git status`、远端、分支和仓库里是否有不应上传的资料。遇到冲突时应暂停自动同步并处理冲突，不要强推或丢弃本地改动。

## 其他常用技能的原仓库

以下技能由各自仓库维护。本合集提供入口链接，**没有复制其代码，也不保证它们已安装在读者电脑上**：

| 技能 | 用途 | 原仓库 |
| --- | --- | --- |
| `product-map-workflow` | 建立产品地图和源码索引，帮助 Agent 定向阅读项目 | [dk1275/product-map-workflow](https://github.com/dk1275/product-map-workflow) |
| `admin-backend-builder` | 构建和修复内容管理后台 | [dk1275/zuo-ge-hou-tai-skill](https://github.com/dk1275/zuo-ge-hou-tai-skill) |
| `gpt-image-2-style-library` | 图片生成风格及提示词参考 | [freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) |
| `archify` | 创建架构图、流程图等可探索图示 | [tt-a1i/archify](https://github.com/tt-a1i/archify) |

`officecli` 和 `frontend-design` 的再发布条件尚未核实，因此没有收入本仓库。这里也没有发布此前移除的 `workbuddy-cli-model-bridge`。

## 公开与安全边界

- 公开前检查技能文件、示例、测试数据和 Git 提交历史；不要提交密钥、令牌、私人仓库地址、个人路径或业务数据。
- 安装技能不等于授权它修改文件或连接外部服务。运行前了解该技能的输入、输出和副作用。
- 第三方技能请从对应原仓库获取，并遵守其许可条款。本仓库根目录的 [MIT 许可证](LICENSE)不改变外部仓库的授权。

欢迎通过 Issue 反馈文档问题。报告问题时请删除日志中的凭据和个人信息。
