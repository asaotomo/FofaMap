# 智能体 MCP 与 Skills 集成

FofaMap 2.0.2 提供一个可回滚的跨宿主安装器、一个通用 Agent Skill，以及兼容 Codex、Claude、Cursor、OpenClaw 和 Grok Build 的插件包。安装器默认把当前 Python 与 `mcp_server.py` 的绝对路径写入 stdio 配置，避免 Cursor 等 GUI 应用因没有继承终端 `PATH` 而出现 `spawn fofamap-mcp ENOENT`；配置中不写入 FOFA 或模型密钥。

## 快速使用

```bash
python -m pip install .
fofamap integrate --list
fofamap integrate --agent all --dry-run
fofamap integrate --agent cursor
```

默认无需手工查找 `fofamap-mcp`。如果宿主必须使用另一套已安装环境，可显式覆盖命令：

```bash
fofamap integrate --agent codex --server-command /absolute/path/to/fofamap-mcp
```

项目级安装写入当前目录；也可以显式指定根目录：

```bash
fofamap integrate --agent claude --scope project --project-root /path/to/project
```

卸载只移除名为 `fofamap` 的 MCP 项和带 `.fofamap-managed.json` 的 Skill/插件：

```bash
fofamap integrate --agent claude --uninstall
```

## 支持矩阵

| 宿主 | MCP | Skills | 安装方式与限制 |
|---|---|---|---|
| Cursor | 原生 | 原生 | 合并 `mcp.json`，安装 Cursor Skill |
| Codex | 原生 | 原生 | 在 `config.toml` 写入带边界标记的 MCP block，安装通用 Skill |
| Claude Code | 原生 | 原生 | 合并 `.mcp.json`/`.claude.json`，安装 Claude Skill |
| OpenCode | 原生 | 原生 | 合并 `opencode.json` 的本地 MCP 项，安装 OpenCode Skill |
| DeepSeek Harness | Tools bridge | 原生 | 生成 Cordis patch；当前 Harness 不消费 MCP Resources/Prompts，账号与字段能力改用 `fofa_account` / `fofa_fields` Tools |
| LM Studio | 原生 | 兼容层 | 合并 `~/.lmstudio/mcp.json` 并输出官方 `lmstudio://add_mcp` deeplink；官方没有 Agent Skills loader |
| OpenClaw | 兼容 Bundle（原生加载） | 兼容 Bundle（原生加载） | user scope 优先调用官方插件生命周期，安装包含 `mcpServers` 与 `skills` 的 Codex-compatible bundle |
| Hermes Agent | 原生 | 原生 | 合并 `~/.hermes/config.yaml`，默认将 server 设为 `trust: untrusted` |
| Grok Build | Claude 兼容插件 | 原生插件 | 安装到 `.grok/plugins`；Grok 自动读取 Claude-compatible MCP/plugin bundle |

`gork`、`claude-code`、`deepseek`、`dsh` 和 `lm-studio` 是命令行别名。

## 默认路径

| 宿主 | user scope | project scope |
|---|---|---|
| Cursor | `~/.cursor/mcp.json`, `~/.cursor/skills/fofamap` | `.cursor/mcp.json`, `.cursor/skills/fofamap` |
| Codex | `~/.codex/config.toml`, `~/.agents/skills/fofamap` | `.codex/config.toml`, `.agents/skills/fofamap` |
| Claude Code | `~/.claude.json`, `~/.claude/skills/fofamap` | `.mcp.json`, `.claude/skills/fofamap` |
| OpenCode | `~/.config/opencode/opencode.json`, `~/.config/opencode/skills/fofamap` | `opencode.json`, `.opencode/skills/fofamap` |
| DeepSeek Harness | `~/.dsh/cordis.patch.yml`, `~/.dsh/skills/fofamap` | `.dsh/fofamap.cordis.yml`, `.dsh/skills/fofamap` |
| LM Studio | `~/.lmstudio/mcp.json`, `~/.lmstudio/skills/fofamap` | LM Studio 配置仍为用户级 |
| OpenClaw | `~/.openclaw/extensions/fofamap` | `.openclaw/extensions/fofamap` |
| Hermes Agent | `~/.hermes/config.yaml`, `~/.hermes/skills/fofamap` | MCP 配置仍为用户级，Skill 使用 `.agents/skills/fofamap` |
| Grok Build | `~/.grok/plugins/fofamap` | `.grok/plugins/fofamap` |

DeepSeek Harness 的 project scope 生成独立 overlay，启动时传入输出中给出的 `--patch` 路径。LM Studio 和 Hermes 的 MCP 配置本身是用户级，因此 project scope 只改变其 Skill 的发现范围（LM Studio 没有官方 Skill 发现机制）。

OpenClaw CLI 可用时，user scope 会调用 `openclaw plugins install/uninstall`，因此 bundle 带安装来源与信任记录；CLI 不可用或使用 project scope 时，安装器退回 OpenClaw 官方支持的扩展发现目录。

## 分发资产

- 通用 Skill：`agent-kit/skills/fofamap/`
- 跨宿主插件：`agent-kit/plugins/fofamap/`
- Codex manifest：`.codex-plugin/plugin.json`
- Claude manifest：`.claude-plugin/plugin.json`
- Cursor manifest：`.cursor-plugin/plugin.json`
- OpenClaw manifest：`openclaw.plugin.json`

Grok Build 会直接读取插件内的 Claude 格式；无需维护第二套 MCP 声明。

## 安全与恢复

- 安装器只写 MCP command/args，不读取或复制 `FOFA_API_KEY`、模型密钥或 bearer token。
- 默认 command/args 固定为执行安装器的 Python 环境和同一安装包中的 MCP 入口；虚拟环境路径不会被解析成缺少依赖的基础 Python。
- 写入配置前会确认当前环境包含 FofaMap 2.0.2 所需的 MCP 2.x SDK；依赖不完整时明确停止，避免产生路径正确但进程无法启动的假成功配置。
- 已存在的配置文件首次修改前备份为 `<name>.fofamap.bak`，之后不会覆盖该备份。
- JSON/YAML 无法安全解析时立即停止，不猜测或重写损坏配置。
- 同名 Skill/插件如果没有 FofaMap 管理标记，默认拒绝覆盖；`--force` 会先移动到 `.fofamap.bak`。
- active Nuclei 扫描仍受 FofaMap MCP 的计划、精确范围和一次性审批机制约束。安装 Skill 不会开启扫描。

## 验证

```bash
fofamap integrate --agent all --dry-run --output-format json
fofamap integrate --agent codex
codex mcp list
fofamap integrate --agent codex --uninstall
```

不同宿主通常需要重启会话或刷新 MCP/插件列表。LM Studio 也可以打开安装器输出的 deeplink；Hermes 可在会话中运行 `/reload-mcp`。

如果早期 2.0.1 配置中仍是 `"command": "fofamap-mcp"`，直接重跑相同的 `integrate` 命令即可升级；安装器会保留其他 MCP 服务和用户配置。

## 上游能力依据

- [Codex MCP](https://developers.openai.com/codex/mcp) 与 [Codex Skills](https://developers.openai.com/codex/skills)
- [Cursor MCP](https://cursor.com/docs/mcp)、[Cursor Skills](https://cursor.com/docs/skills) 与 [Cursor Plugins](https://cursor.com/docs/plugins)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp) 与 [Claude plugins](https://code.claude.com/docs/en/plugins)
- [OpenCode MCP](https://opencode.ai/v2/docs/mcp-servers) 与 [OpenCode Skills](https://opencode.ai/docs/skills)
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
- [LM Studio MCP deeplink](https://lmstudio.ai/docs/app/mcp/deeplink)
- [OpenClaw plugin manifest](https://github.com/openclaw/openclaw/blob/main/docs/plugins/manifest.md)
- [Hermes MCP config](https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference)
- [Grok Build skills, plugins and marketplaces](https://docs.x.ai/build/features/skills-plugins-marketplaces)

## AI 全程安装与 .skill 分发

[官方复制提示词及通用宿主接入](AI_INSTALL.md) 支持让当前 AI 完成下载、环境、账号引导、当前宿主配置与实际加载检查。专用安装器的支持范围仍以本文矩阵和 `fofamap integrate --list` 为准。

MCP 服务支持 stdio、旧 SSE 和 Streamable HTTP；`http` 是 Streamable HTTP 别名。使用 `fofamap-mcp --check` 检查真实 stdio 握手，使用 `--check-url` 检查已经启动的 HTTP/SSE 服务。检查不会调用 FOFA 或模型。

通用 Skill 分发包位于 [agent-kit/fofamap.skill](../agent-kit/fofamap.skill)。可运行 `fofamap integrate --export-skill ./fofamap.skill` 导出；`fofamap integrate --agent codex --import-skill ./fofamap.skill` 仅导入 Skill，不修改 MCP。原生导入 UI 取决于宿主；LM Studio 使用兼容层，OpenClaw/Grok 使用插件包。
