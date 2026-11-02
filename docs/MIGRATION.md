# Migrating from FofaMap 2.0 to 2.0.1

## Credentials and configuration

Copy `config/settings.example.yaml` to `config/settings.yaml`, or run `fofamap init`. Environment variables, Keyring and container secrets remain preferred. If Keyring is unavailable, the wizard can write FOFA and model keys to the local YAML only after explicit confirmation; the default path is gitignored. On macOS/Linux it applies `0600` permissions. Windows relies on the current user directory ACL and the wizard warns that Keyring or environment variables are safer. `FOFA_KEY` remains a temporary compatibility alias; `FOFA_EMAIL` is optional for current key-only FOFA endpoints. A missing YAML file is valid.

Keys found in YAML still load with a warning. Any key that was ever committed must be rotated; a newly confirmed local-only key may remain only while the file stays private and untracked.

## CLI

The frequently used 2.0 aliases remain:

```bash
fofamap -q 'app="nginx"' -f host,ip,port,status_code -p 3
fofamap -hq 8.8.8.8
fofamap -cq 'app="redis"' -f country,port
fofamap -ai '统计中国公开的 Redis 服务分布'
```

Running `fofamap` without arguments restores the full interactive wizard. Passing a classic option without its value, such as `fofamap --query`, prompts for the value instead of failing. Human-readable Rich tables and automatic XLSX export are the defaults; raw JSON is opt-in through `--output-format json` or `jsonl`.

The CLI is a standalone product entry point: ordinary search, Host, stats, icon and batch modes do not start MCP/REST and do not require a model provider. MCP remains a parallel integration entry point backed by the same typed FOFA core.

`-n/--nuclei` creates a bounded plan after search and can run it only after showing the exact targets, template IDs and severities and receiving interactive approval. MCP/REST use the equivalent independent `nuclei_plan` then `nuclei_execute` flow.

The old internal `core.ai`, `core.handler`, and duplicate `core.core.FofaClient` implementations are removed. `core.core.FofaClient` remains a re-export, but other internal Python APIs are not compatibility guarantees.

## MCP

2.0.1 requires `mcp>=2,<3` and uses `MCPServer`. The SDK negotiates older supported protocol revisions with clients. Update installation before importing `mcp_server.py`.

```bash
fofamap-mcp                         # stdio
fofamap-mcp --transport streamable-http --host 127.0.0.1 --port 8001
```

## Agent/model configuration

Providers are profiles, not branches in Agent code. Choose `openai_responses`, `openai_chat`, `anthropic_messages`, or `ollama_native`, then set any current or future model ID. Cross-provider fallback is off until explicitly configured.
