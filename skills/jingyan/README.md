# jingyan｜经验传承

把项目中**有证据、可复用**的做法整理成方法库，并在后续任务中按适用范围取用。它不会把一段聊天或一次成功尝试直接认定为通用规则。

## 适合什么时候用

- 一个项目的排错、部署或交付过程产生了可复用经验。
- 新任务需要查找过去已批准、适用的做法。
- 需要记录任务使用了哪些方法、实际验证结果，以及仍未解决的问题。

一次性问答或没有可复用证据的任务，不必强行建立经验条目。

## 依赖与准备

- Python 3。
- 一个**由你自己选择**的经验库目录；本仓库不包含作者的个人经验库。
- 源项目记录或其他可核实证据。提取过程只读取源项目，除非用户另外授权修改它。

将本目录安装到 Agent 的技能目录后，先在仓库根目录运行：

```bash
python3 skills/jingyan/scripts/experience_tool.py --root /path/to/experience-library init
python3 skills/jingyan/scripts/experience_tool.py --root /path/to/experience-library status
python3 skills/jingyan/scripts/experience_tool.py --root /path/to/experience-library policy show
```

`/path/to/experience-library` 是示例占位路径，换成你自己的目录。`init` 会创建或初始化经验库，请先确认目标位置。完整参数见[SKILL.md](SKILL.md)；命令实现见[scripts/experience_tool.py](scripts/experience_tool.py)。

## 一次任务的闭环

1. **提取候选**：从项目记录中提取经验，或手动添加候选。候选默认是 `pending`，不是已验证方法。
2. **按策略审批**：先查看 `policy show`。`manual` 模式需要逐项审批；`bootstrap_auto` 只能在用户明确授予该长期权限后使用。
3. **任务前注入**：用 `inject` 检索适用的已批准方法，保存返回的注入 ID。
4. **任务后复盘**：用同一个注入 ID 执行 `retro`，记录实际结果、验证状态和未完成项。
5. **检查闭环**：运行 `closure --project <project>`；不要把仍有开放注入记录的任务报告为闭环完成。

批准的方法仍有适用范围和排除条件，不能代替当前项目的证据。不要把多个 Agent 的一致说法当作验证。

## 数据与安全

经验库是长期数据，会保留候选、批准决定和任务记录。写入前审查来源；不要放入密钥、令牌、真实个人标识或不必要的客户信息。脚本有常见凭据模式检查，但不能替代人工判断。

## 文件

- [SKILL.md](SKILL.md)：使用规则及常用命令。
- [scripts/experience_tool.py](scripts/experience_tool.py)：本地命令工具。
- [tests/test_experience_tool.py](tests/test_experience_tool.py)：工具测试。
