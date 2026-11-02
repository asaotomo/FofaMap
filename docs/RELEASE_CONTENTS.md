# 发行包目录说明 / Release contents

公开源码与用户发行包保留完整应用、安装更新能力和双语说明。测试、构建工具、内部复测报告和本地个人数据不随本版本上传。

Public source and the user archive retain the complete application, installers/updater and bilingual documentation. Tests, build tooling, internal reports and local personal data are not uploaded with this release.

| 文件或目录 / Path | 用途 / Purpose |
|---|---|
| `fofamap.py` | 命令行、交互向导、账号和模型配置 / CLI, wizard and setup |
| `mcp_server.py` | MCP 工具、资源及传输入口 / MCP tools, resources and transports |
| `config/` | 配置加载、默认模板 / Configuration and defaults |
| `core/` | FOFA 客户端、规则、Agent、报告、扫描和集成 / Core application features |
| `providers/` | 多家模型接口和路由 / Model adapters and routing |
| `service/` | REST、计划任务、鉴权和存储 / REST, scheduling, authentication and storage |
| `utils/` | 终端界面、输出、账号引导和更新检查 / Terminal UI, onboarding and updater |
| `agent-kit/` | Skill、插件及导入导出包 / Skill and plugin installation/export assets |
| `scripts/` | 仅保留安装/修复/卸载管理、自检、命令注册、更新工作进程、下载校验信息和 README 实操程序 / Installation/update support and documented tutorials |
| `examples/` | README 使用的查询和计划任务输入 / Documented query and schedule inputs |
| `docs/` | 使用说明、截图、规则依据、安全与迁移说明 / Documentation, screenshots, rule provenance and policies |
| `pyproject.toml` | 安装依赖与命令入口的唯一应用元数据 / Installation dependencies and command entry points |
| `install.*`、`start.*` | Windows、macOS、Linux 安装与启动入口，保留兼容用法 / Platform installers and launchers |
| `.env.example`、`.gitignore`、`LICENSE` | 参数说明、避免误提交密钥、许可证 / Configuration reference, secret ignore rules and license |

`tests/`、多轮 `live_*` 复测脚本、截图生成工具、构建工具、内部复测报告和重复依赖清单不放入公开源码或用户包。仓库保留必要的安装/接口自检与安全检查工作流；`.github/` 不放入用户 ZIP。`SECURITY.md` 和 `MIGRATION.md` 统一收纳到 `docs/`，文档链接会同步调整。

Tests, repeated acceptance scripts, image/build tooling, internal reports and duplicate dependency lists are omitted from public source and user archives. The repository retains installation/interface and security workflows; `.github/` is omitted from the user ZIP. Security and migration guides are placed under `docs/`, with local links adjusted.

README 的实操程序与截图仍保留；安装自检直接使用应用能力，不依赖未公开的测试目录。`agent-kit` 内的 Skill 目录、插件内副本和 `.skill` 文件服务于不同宿主和导入方式，不能把它们当作重复文件直接删除。

Documented tutorial programs and screenshots remain available. Installation checks use application capabilities without depending on unpublished test directories. Skill directories, plugin copies and the `.skill` archive support different host/import mechanisms and are intentionally retained.

一键更新优先使用正式发行源码附件；回退下载开发仓库归档时，也会应用同一份用户包清单。已有配置、密钥、报告、数据库和虚拟环境保留。程序更新后，只清理已经空置的程序目录，不删除含有用户文件的目录。

Automatic updates use the same user-package policy when falling back to a repository archive. User configuration, credentials, reports, databases and the virtual environment are preserved; only empty application directories are removed.

用户包中的 Python 运行文件和运行资源均与发布源码逐字节核对。发行页面提供 `SHA256SUMS`，可验证下载文件的完整性。
