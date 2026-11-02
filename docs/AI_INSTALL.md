# 让 AI 安装 FofaMap MCP 与 Skill

版本 2.0.2。把下面提示词复制给具有终端、文件修改或 MCP 配置权限的 AI。适用于 Codex、Cursor、WorkBuddy、TeleAgent、LM Studio、zCode、Claude Code、DeepSeaNtry、Gemini CLI、OpenCode、OpenClaw、Hermes、Hx0 天眼等；这是一条通用安装任务，宿主的实际自动化权限决定是否需要用户协助。它不代表每个宿主都有内置专用安装器。

## 官方复制提示词

```text
请为当前 AI 宿主安装并验证 FofaMap MCP 和配套 Skill，官方仓库：https://github.com/asaotomo/FofaMap 。先检查本机是否已安装；未安装则从官方仓库下载当前版本，使用 Python 3.10+ 和独立虚拟环境安装，阅读仓库 README、AGENTS.md 和 agent-kit/skills/fofamap/SKILL.md 后执行。保留现有 MCP 配置和密钥，修改前备份。运行 fofamap integrate --list，若当前宿主有专用安装器，只安装当前宿主；否则先查该宿主的官方 MCP 配置方式，使用本机 Python 和 mcp_server.py 的绝对路径接入 stdio，或连接本机 Streamable HTTP / SSE，不猜配置路径，不声称尚未完成的步骤已成功。

没有 FOFA 账号时引导我到 https://fofa.info/ 注册并查看 https://fofa.info/api/introd 和 https://fofa.info/vip；没有配置邮箱或 API Key 时，引导我在本机 fofamap init 中安全输入，避免把密钥发到聊天、命令历史、日志或公共配置。账号权限按实际 vip_level 判断：注册用户无 Host/Stats，个人和教育账户无 Stats，不把权限错误当成账号无效或 0 结果。只用宿主模型完成理解和报告时不要求另配模型 Key；我明确选择 FofaMap 自带 Agent 时再引导配置模型。

检查 Nuclei：只做 FOFA 测绘可继续使用；需要扫描但尚未安装时，先询问我是否同意自动安装；仅在我选 Y 时按当前操作系统从 https://github.com/projectdiscovery/nuclei 的官方方式安装并验证 nuclei -version，选 N 则留给我手动安装。不要自动扫描、公开服务端口或修改其他宿主。Skill 优先使用专用安装器；支持 .skill 的宿主也可导入官方包，不支持该后缀时按宿主官方规则安装其中的 fofamap 目录，LM Studio 的 Skill 加载取决于宿主扩展。

完成后运行 fofamap --version、绝对入口 python /path/to/FofaMap/mcp_server.py --check，并核对输出的 Python/入口/状态目录与源码指纹，避免旧 site-packages 遮蔽；再运行 fofamap integrate --agent 当前宿主 --check-stale，确认 Skill 的内容与版本一致；再通过当前宿主实际列出 MCP 工具并调用 fofa_validate_query 和 fofa_fields。配置好 FOFA 后再执行 fofa_account，最后用 domain="baidu.com" 只读查询 1 条验证，禁用存活探测、不执行 Nuclei。汇报版本、Python 路径、MCP 配置位置、传输方式、Skill 位置、工具数和各项验证结果；无法自动完成时准确说明缺少什么，只有通过连接与工具调用才算安装完成。
```

## 可执行命令

```bash
# 进入已经下载的官方源码目录
python3 -m venv .venv
# macOS/Linux
. .venv/bin/activate
# Windows PowerShell 改用 .venv\Scripts\Activate.ps1
python -m pip install .
fofamap integrate --list
fofamap integrate --agent cursor           # 只选当前宿主；也可用 codex / claude 等
fofamap-mcp --check                        # 真正连接 stdio，不消耗 FOFA 额度
```

安装器内置目标以 `integrate --list` 为准。WorkBuddy、TeleAgent、zCode、DeepSeaNtry、Gemini CLI、Hx0 天眼等未列入专用安装矩阵的宿主，使用其官方的通用 MCP 接入流程。首次配置可运行 `fofamap init`，后续在向导中选择修改账号、模型或常用配置。

## 三种传输

| 模式 | 启动命令 | 宿主连接方式 |
|---|---|---|
| stdio（本机默认） | `fofamap-mcp` | 宿主启动绝对路径的 Python + mcp_server.py；无需常驻 HTTP 服务 |
| Streamable HTTP（推荐 HTTP） | `fofamap-mcp --transport streamable-http --host 127.0.0.1 --port 8001` | `http://127.0.0.1:8001/mcp` |
| HTTP 别名 | `fofamap-mcp --transport http --port 8001` | 与 Streamable HTTP 相同 |
| 旧版 SSE | `fofamap-mcp --transport sse --host 127.0.0.1 --port 8002` | `http://127.0.0.1:8002/sse`，发送端点 `/messages/` 由握手提供 |

服务运行后在另一终端检查：

```bash
fofamap-mcp --check-url http://127.0.0.1:8001/mcp
fofamap-mcp --check-url http://127.0.0.1:8002/sse
```

`--check` 验证 MCP 服务连接及本地工具，不替代宿主自身的加载验证或 FOFA 鉴权。HTTP/SSE 非回环监听沿用令牌及 issuer/resource 配置要求，具体见 README 的服务鉴权部分。多个独立进程共用同一 FOFA 账号时，需自行协调总调用速率。

## .skill 分发与导入

仓库提供 [fofamap.skill](../agent-kit/fofamap.skill)，内容是 `fofamap/SKILL.md`、引用资料及元数据，不包含配置文件或密钥。兼容宿主可在 Skill 导入界面选择此文件；不是所有宿主都支持 `.skill` 导入按钮。

```bash
# 从当前安装包导出，目标文件必须不存在
fofamap integrate --export-skill ./fofamap.skill

# 仅导入 Skill，不修改 MCP。先用 --dry-run 预览
fofamap integrate --agent codex --import-skill ./fofamap.skill --dry-run
fofamap integrate --agent codex --import-skill ./fofamap.skill
```

Cursor、Codex、Claude Code、OpenCode 等使用安装器给出的 Skill 路径。OpenClaw/Grok 使用插件包，应运行 `fofamap integrate --agent openclaw` 或 `--agent grok`。同名非托管 Skill 不会直接覆盖；如要替换，检查后使用 `--force`，程序保留备份。

## 升级与连接核验

使用一键安装器安装后，运行 `fofamap --update` 更新；手动 pip 安装请沿用原包管理方式。升级后重新连接宿主 MCP，并检查 Skill 是否过期。已连接的宿主需要自行刷新或重启 MCP；服务端不能替第三方客户端重新加载。

```bash
fofamap-mcp --check --expect-version 2.0.2 --expect-build-date 2026-11-02
fofamap integrate --agent cursor --check-stale --json
# 只更新指定宿主的 Skill；其他宿主替换 agent 名称
fofamap integrate --agent cursor --import-skill agent-kit/fofamap.skill --json
fofamap integrate --agent cursor --check-stale --json
```
