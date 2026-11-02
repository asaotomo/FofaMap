# 2.0.2 默认模型与配置入口 / Default models and setup

核验日期 / Verified: **2026-11-02**。模型 ID 按官方 API 文档记录；实际可用权限以当前账号的实时模型列表为准。没有使用各家密钥执行收费生成请求，协议参数由离线 HTTP 回归验证。

| 提供商 / Provider | 默认模型 ID / Default model | API Base URL | 密钥变量 / Key variable | 官方依据 / Source |
|---|---|---|---|---|
| **DeepSeek（默认推荐 / Recommended default）** | `deepseek-flash` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | [Change log](https://api-docs.deepseek.com/updates/) |
| OpenAI | `gpt-6.1-sol` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | [OpenAI Docs](https://developers.openai.com/api/docs/guides/latest-model) |
| Claude | `claude-opus-5-5` | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | [Models](https://platform.claude.com/docs/en/models/overview) |
| Kimi | `kimi-k3.1-pro` | `https://api.moonshot.cn/v1` | `MOONSHOT_API_KEY` | [Kimi K3.1 Pro](https://platform.kimi.com/docs/guide/kimi-k3-1-pro-quickstart) |
| MiniMax（中国 / China） | `MiniMax-M3.1-Flash` | `https://api.minimax.cn/v1` | `MINIMAX_API_KEY` | [Model API](https://platform.minimax.cn/docs/guides/text-generation) |
| 小米 MiMo | `mimo-v2.6-pro` | `https://api.xiaomimimo.com/v1` | `MIMO_API_KEY` | [Models](https://mimo.mi.com/docs/en-US/quick-start/model) |
| GLM / 智谱 | `glm-5.3` | `https://open.bigmodel.cn/api/paas/v4` | `ZHIPU_API_KEY` | [GLM-5.3](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3) |
| 硅基流动 / SiliconFlow | `deepseek-ai/DeepSeek-V4-Flash` | `https://api.siliconflow.cn/v1` | `SILICONFLOW_API_KEY` | [Official integration defaults](https://docs.siliconflow.cn/docs/usercases/use-siliconcloud-in-metis) · [Models API](https://docs.siliconflow.cn/docs/api/models-get) |
| Grok | `grok-4.7` | `https://api.x.ai/v1` | `XAI_API_KEY` | [Grok 4.7](https://docs.x.ai/developers/models/grok-4.7) |
| Gemini | `gemini-4-argon` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` | [Latest model](https://ai.google.dev/gemini-api/docs/latest-model) |

DeepSeek 的 `deepseek-flash` 是官方跟随最新版本的别名，当前对应 V4.1 Flash 更新，不应因名字没有版本号就替换成旧的 `deepseek-v4-flash`。硅基流动是托管平台，模型 ID 与原厂不同，应保留完整的组织前缀和大小写。

`deepseek-flash` follows the latest official Flash release. SiliconFlow model IDs use the hosting platform's full IDs, including organization prefixes and case.

新版本的思考参数需要同时适配：OpenAI Sol/Astra、Kimi K3.1 Pro 和 GLM-5.3 不支持关闭思考；选择最低强度 `low`。当前 Claude 默认使用 adaptive thinking 和 `output_config.effort`，不继续发送旧的手动思考预算。MiMo 2.5 已于 2026-10-21 下线，默认切换到 2.6 系列。

Current always-on reasoning models use supported effort levels; the default is `low`. Claude uses adaptive thinking and `output_config.effort`. MiMo 2.5 was retired on October 21; defaults now use 2.6.

在主菜单选择 **设置与维护 → AI 模型配置**，会补齐缺少的云服务预设，并更新仍使用原厂地址的旧内置默认模型，保留密钥、路由和自定义模型/网关。打开配置页会先保存这次默认配置更新并显示更新名单。Ollama / LM Studio 从本机实际安装的列表中选择，不猜测本地模型版本。

Choose **Settings → AI model setup** in the wizard to refresh shipped defaults and add missing provider profiles while preserving credentials, routing, and custom gateways/models. Local models come from the local server's actual catalog.

账号与模型分步引导入口为 `fofamap --setup`。安装器第 **6/6** 步也会进入该引导，已保存的 Key 会实际验证；不再仅凭 Key 非空就跳过。输入仍为交互终端时，即使输出被 PowerShell 或 tee 接管，也继续显示引导。

Run `fofamap --setup` for guided account/model configuration. Installer step **6/6** starts the same flow and checks saved credentials. Capturing stdout does not suppress prompts when an interactive keyboard remains available.
