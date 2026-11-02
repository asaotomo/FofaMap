# macOS / Linux 手动安装

安装第一步选择简体中文 / English；之后的账号引导与日常界面沿用所选语言。需要切换时：设置与维护 → 界面语言，无需手改 YAML。自动安装可传 `-Language en`（Windows）或 `--language en`（macOS/Linux）。

安装器现支持安装、修复、卸载：首次运行选安装；已有安装选修复或卸载，`0` 取消。修复会重装依赖并恢复命令入口；卸载不需要 Python 或网络，保留源码、配置、密钥、结果、报告、数据库及备份。无人值守可用 `install.bat -Action install|repair|uninstall`（Windows）或 `bash install.sh --action install|repair|uninstall`（macOS/Linux），竖线表示三选一，不是命令的一部分。详见 [安装管理说明](../README.md#安装修复与卸载)。

推荐使用 [README 的一键安装](../README.md#install)。本文用于自定义环境和排错。

### macOS / Linux：四步安装

以下命令逐行执行。截图来自一份全新隔离源码目录的实际安装。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
fofamap --version
```

<details>

<summary>查看实操结果：macOS / Linux：四步安装</summary>

![macOS / Linux：四步安装](https://camo.githubusercontent.com/5edd4b75c1dd373838248906bb64c4bbe259ec586200f06d506ad409820a509b/68747470733a2f2f7261772e6769746875622e636f6d2f6173616f746f6d6f2f466f66614d61702f626464626135336330623862636133316466663337393263323734636537363435343964353333362f646f63732f6173736574732f726561646d652f322e302e322f656e2f696e7374616c6c2e706e67)

</details>

最后看到 `FofaMap, version 2.0.2` 才表示版本对了。每次新开终端，要在项目目录重新激活 `.venv`；也可直接运行 `.venv/bin/fofamap`。如果你看到 2.0.1，说明仍在运行已发布旧版或另一个 Python 环境。
