# Windows 安装与排错

安装第一步选择简体中文 / English；之后的账号引导与日常界面沿用所选语言。需要切换时：设置与维护 → 界面语言，无需手改 YAML。自动安装可传 `-Language en`（Windows）或 `--language en`（macOS/Linux）。

安装器现支持安装、修复、卸载：首次运行选安装；已有安装选修复或卸载，`0` 取消。修复会重装依赖并恢复命令入口；卸载不需要 Python 或网络，保留源码、配置、密钥、结果、报告、数据库及备份。无人值守可用 `install.bat -Action install|repair|uninstall`（Windows）或 `bash install.sh --action install|repair|uninstall`（macOS/Linux），竖线表示三选一，不是命令的一部分。详见 [安装管理说明](../README.md#安装修复与卸载)。

[English](INSTALL_WINDOWS_EN.md) · [返回 README](../README.md#install)

推荐双击源码目录里的 `install.bat`。安装后自动注册当前用户 PATH，新开 CMD / PowerShell，在任意目录输入 `fofamap` 即可打开，也能双击 `start.bat`。首次使用或配置损坏时，安装结束直接进入账号配置，保存并验证后可继续配置模型。安装器选择兼容的 x64 Python；Windows 11 ARM 也使用这一环境。下方手动步骤用于排错和自定义环境。

**关于 `fofamap.exe`：**源码 ZIP 不自带独立 EXE。`pip install -e .` 会根据 [pyproject.toml](../pyproject.toml) 的 `[project.scripts]` 自动在 `.venv\Scripts` 生成这个启动器；也可以直接用 `.\.venv\Scripts\python.exe .\fofamap.py`，两者进入相同的 CLI。

一键安装器会复制生成的启动器到 `%LOCALAPPDATA%\FofaMap\bin\fofamap.exe` 并写入当前用户 PATH；不使用会截断 PATH 的 `setx`，不需要管理员权限。重复安装不会重复添加同一项。手动安装要获得相同短命令，可在完成 pip 安装后执行 `python scripts/register_command.py`。在 CMD 中运行 `install.bat` 后会刷新该 CMD 的 PATH；安装前已经打开的其他终端需要重新打开。不要删除安装目录及 `.venv`，移动目录后重新安装。

后续执行 `fofamap --update` 检查 GitHub 最新正式版并自动下载源码、备份、安装、验证和修复命令入口。Windows 会打开独立更新窗口，等旧启动器退出后进行安装，请等待窗口显示完成。更新保留账号配置和报告；失败时恢复旧源码并尝试恢复旧环境，日志位于 `.fofamap-updates`。详见 [一键更新](../README.md#upgrade)。

<a id="windows-install"></a>


**ARM64 注意：**截图中的 `cryptography` 源码构建 / `cffi>=2.0.0` 错误，来自原生 ARM64 依赖链缺少匹配的包或镜像同步问题。Windows 11 ARM 请优先用 `install.bat`，它自动选择 x64 Python，不要求用户安装 Rust/C++。下方手动流程要求 Python 的 `sysconfig.get_platform()` 返回 `win-amd64`，不是 `win-arm64`；`py -3` 在 ARM 机器上可能选到原生 ARM64 Python，不能仅凭“64 位”就认为等价。

### Windows 10 / 11：从安装 Python 到第一次查询

以下在 **PowerShell / Windows Terminal 的 PowerShell 标签页**中执行；不要在 Python 的 `>>>` 窗口里输入。推荐使用 **64 位 Python**。正文的 macOS 实操图不作为 Windows 安装截图。

**第 1 步：安装并确认 Python。** 从 [Python Windows 官方下载页](https://www.python.org/downloads/windows/) 安装 Python。已安装 Python 3.10 或以上的用户可以跳过下载。

- 使用新版 **Python install manager**：安装后重新打开 PowerShell，执行下面的 `py install 3.13`，安装 Python 3.13 的可用维护版本。这个子命令只适用于新版管理器；传统 Python Launcher 没有 `install` 命令。
- 使用传统 `.exe` 安装器：选择 64 位安装包，保留 `pip` 和 Python Launcher；安装器提供 `Add python.exe to PATH` 时勾选它。安装完成后重新打开 PowerShell，再验证版本。

```powershell
# 仅新版 Python install manager 需要这一行；已有合适版本则跳过
py install 3.13

# 应显示 Python 3.10 或以上
py -3 --version
```

如果 `py` 不存在，但 `python --version` 正常显示 3.10+，下面创建环境时把 `py -3` 换成 `python` 即可。后续统一使用项目 `.venv` 内的 Python，与系统里有多少个 Python 无关。官方说明：[Windows 安装](https://docs.python.org/3/using/windows.html)、[venv 虚拟环境](https://docs.python.org/3/library/venv.html)。

**第 2 步：解压源码并进入正确文件夹。** 将 2.0.2 源码 ZIP **全部解压**，例如放在 `C:\Tools\FofaMap`。不要直接在压缩包预览里运行，也不要把外层下载目录误当项目根目录。打开实际包含 `pyproject.toml`、`fofamap.py` 的文件夹，在地址栏输入 `powershell` 并回车；也可在已打开的 PowerShell 中执行：

```powershell
# 把这个路径换成你实际解压的位置；有空格也保留引号
Set-Location -LiteralPath 'C:\Tools\FofaMap'
Get-ChildItem pyproject.toml, fofamap.py
```

应能列出这两个文件。提示找不到文件时，先修正目录，再继续安装。

**第 3 步：创建环境并安装。** 以下写法直接指定虚拟环境中的程序，**不用先激活**，不会遇到 `Activate.ps1` 的脚本执行策略问题。通常不需要管理员权限。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\fofamap.exe --version
```

看到 `FofaMap, version 2.0.2` 后继续。`Successfully installed` 是依赖安装成功的提示；如果中途有错误，不要跳过错误直接运行后面的业务命令。只有已经发布的 2.0.1 源码时，安装结果仍然是 2.0.1。

**第 4 步：配置 FOFA。** 在同一个项目目录运行初始化向导，选择界面语言，按提示填写 FOFA 账号和 API Key。普通资产查询不需要模型 Key；先验证 FOFA，再按需要配置模型。

```powershell
.\.venv\Scripts\fofamap.exe init
```

凭据存储方式、模型设置与下文[初始化说明](../README.md#configure)一致。不要把密钥写进截图、聊天或示例文件。

**第 5 步：做第一次查询。** 最容易上手的是交互向导：运行下面的命令，选择普通资产检索，粘贴 `domain="baidu.com"`，将页数设为 1，返回字段选默认固定字段或智能选择，历史数据/导出高级选项选 N，不选择 Nuclei 扫描。每页条数沿用当前偏好；要明确限制最多 3 条，用下方命令。向导内输入查询不经过 PowerShell 的引号解析。

```powershell
.\.venv\Scripts\fofamap.exe
```

希望直接复制一条命令的用户，可使用下面 **Windows PowerShell 5.1 / PowerShell 7 通用**的写法。`--%` 是 Windows PowerShell 的停止解析标记；后面的 `\"` 用来把真正的双引号传给程序。**整行复制，不要换行，也不要在后面接 PowerShell 管道或变量。** 详见 [Microsoft 参数解析说明](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_parsing)。

```powershell
.\.venv\Scripts\fofamap.exe --% -q domain=\"baidu.com\" -f host,ip,port,title --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save
```

这条命令只查 FOFA 索引，最多返回 3 条，不执行存活检测或扫描。看到结果表或明确的上游错误即可判断执行情况；没有命中不等于安装失败。

**第 6 步：以后怎么启动、升级。** 每次打开 PowerShell，先进入项目目录，再执行 `.venv\Scripts\` 对应入口（下面示例带齐开头的 `.`）。这套写法无需重复激活或重复安装。

```powershell
Set-Location -LiteralPath 'C:\Tools\FofaMap'
.\.venv\Scripts\fofamap.exe --version
.\.venv\Scripts\fofamap.exe
```

更新到维护者提供的新源码后，在新项目目录重新执行第 3 步。不要把旧 `.venv` 整个复制到新目录；虚拟环境中的入口可能仍指向旧路径。备份你自己的配置和报告，再切换实际使用的源码。

**可选：激活后使用短命令。** 希望直接输入 `fofamap` 时，可以运行 `.\.venv\Scripts\Activate.ps1`（完整命令如下）；成功后提示符通常带 `(.venv)`，用 `deactivate` 退出。若提示“无法加载 / 禁止运行脚本”，回到上面的免激活方式即可，无需为安装 FofaMap 修改整机策略。

```powershell
.\.venv\Scripts\Activate.ps1
fofamap --version
# 结束后退出虚拟环境
deactivate
```

| 遇到的情况 | 处理方法 |
|---|---|
| `py` / `python` 不是可识别的命令 | 安装官方 Python 后重新打开 PowerShell；检查安装器的 Launcher / PATH 选项。只有 `python` 可用时，用它创建 `.venv`。 |
| 输入 `python` 后打开商店或版本不对 | 先检查 `py -3 --version`；使用已安装的 Python 创建环境，再一直用 `.venv\Scripts\python.exe`。 |
| 提示没有 `pyproject.toml` / 不是 Python 项目 | 回到真正包含 `fofamap.py` 的源码根目录，确认 ZIP 已全部解压。 |
| 找不到 `.venv\Scripts\python.exe` | 环境创建没有成功或当前目录错误；先看第 3 步第一条命令的错误。 |
| 提示 `pip` 不存在 | 使用完整的 `.venv\Scripts\python.exe -m pip`，不要单独执行系统 `pip`；创建环境时不要加 `--without-pip`。 |
| 提示激活脚本被禁止 | 使用本文的免激活命令；运行 CLI 不依赖激活脚本。 |
| 依赖下载超时、代理或证书错误 | 先确认能访问 PyPI / 公司批准的依赖源，按网络环境配置代理或受信任证书后重试。 |
| 出现编译器 / 没有匹配 wheel 的错误 | 先升级当前 `.venv` 的 pip，确认使用受支持的 64 位 CPython；不要使用嵌入版 Python。 |
| 路径里有空格 | `Set-Location -LiteralPath '完整路径'`；运行带空格的绝对程序路径时用 `& 'C:\带空格的目录\.venv\Scripts\fofamap.exe' --version`。 |
| 查询引号丢失 / 出现语法错误 | 先用交互向导；直接执行时按上面的 `--%` 整行写法。不要把 Bash 的单引号示例直接当作所有 PowerShell 版本的等价写法。 |
| 显示旧版或运行了另一个环境 | 使用当前源码目录内的 `.venv\Scripts\fofamap.exe --version`；用 `Get-Command fofamap -All` 检查短命令实际指向哪里。 |
| 中文乱码 | 在 Windows Terminal 中使用支持中文的字体；先在向导里切换英文界面确认是否只是显示问题。 |
