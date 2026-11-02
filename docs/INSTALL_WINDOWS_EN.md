# Windows installation and troubleshooting

Choose Chinese / English as the first installer step. The account guide and future sessions use this language. Change it later under Settings → Interface language; no YAML editing is required. Automation accepts `-Language en` (Windows) or `--language en` (macOS/Linux).

The installer supports install, repair and uninstall: first use offers Install; existing installations offer Repair or Uninstall; `0` cancels. Repair reinstalls dependencies and restores the command. Offline uninstall needs no Python and retains source, settings, keys, results, reports, databases and backups. Automation: `install.bat -Action install|repair|uninstall` (Windows) or `bash install.sh --action install|repair|uninstall` (macOS/Linux); the pipe denotes alternatives and is not part of the command. See [installation management](../README_EN.md#install-repair-and-uninstall).

[中文](INSTALL_WINDOWS.md) · [Back to README](../README_EN.md#install)

Double-click `install.bat` in the extracted source directory. It registers the current user's PATH; open a new CMD/PowerShell window and run `fofamap` from any directory, or double-click `start.bat`. First use or damaged configuration opens account setup immediately after installation, followed by verification and optional model setup. The installer chooses compatible x64 Python, including on Windows 11 ARM. Manual steps below are for troubleshooting and custom environments.

**Where `fofamap.exe` comes from:** the source ZIP does not contain a standalone EXE. `pip install -e .` generates this launcher in `.venv\Scripts` from `[project.scripts]` in [pyproject.toml](../pyproject.toml). Running `.\.venv\Scripts\python.exe .\fofamap.py` enters the same CLI directly.

The installer copies that generated launcher to `%LOCALAPPDATA%\FofaMap\bin\fofamap.exe` and registers its directory in the user PATH. It avoids `setx` truncation, requires no administrator rights, and does not duplicate its PATH entry. After manual pip installation, `python scripts/register_command.py` performs the same registration. Running `install.bat` inside CMD also refreshes that CMD's PATH; other terminals already open before installation should be reopened. Keep the source directory and `.venv`; rerun installation after moving them.

Use `fofamap --update` for later stable GitHub releases: it downloads source, backs up code, reinstalls, verifies, and repairs the command. Windows opens a separate update window after the existing launcher exits; wait for completion. Configuration and reports are preserved. Failures restore old source and attempt to restore the previous package environment; logs are under `.fofamap-updates`. See [one-command updates](../README_EN.md#upgrade).

<a id="windows-install"></a>


**ARM64 note:** the reported `cryptography` source-build / `cffi>=2.0.0` failure involves native ARM64 dependency availability and possibly mirror synchronization. On Windows 11 ARM, prefer `install.bat`, which chooses x64 Python without requiring Rust/C++. The manual route below requires `sysconfig.get_platform()` to report `win-amd64`, not `win-arm64`; `py -3` can select native ARM64 Python on an ARM host.

### Windows 10 / 11: install Python, set up FofaMap, and run a first query

Run these commands in **PowerShell**, including a PowerShell tab in Windows Terminal. Do not enter them at Python’s `>>>` prompt. Use **64-bit Python**. The macOS task images in this guide are not Windows installation screenshots.

**Step 1: install and verify Python.** Download Python from the [official Windows download page](https://www.python.org/downloads/windows/). Skip the download if Python 3.10 or later is already installed.

- With the new **Python install manager**, reopen PowerShell after installing the manager, then use `py install 3.13` below to install an available maintained Python 3.13 runtime. This subcommand belongs to the new manager; the traditional Python Launcher does not have an `install` command.
- With a traditional `.exe` installer, choose the 64-bit package and keep `pip` and the Python Launcher selected. Select `Add python.exe to PATH` if offered. Reopen PowerShell after installation, then check the version.

```powershell
# New Python install manager only; skip if a suitable runtime already exists
py install 3.13

# Must report Python 3.10 or later
py -3 --version
```

If `py` is unavailable but `python --version` reports 3.10+, replace `py -3` with `python` when creating the environment below. Subsequent commands use the Python inside this project’s `.venv`, so multiple system installations do not affect them. Official references: [Windows installation](https://docs.python.org/3/using/windows.html), [venv environments](https://docs.python.org/3/library/venv.html).

**Step 2: extract the source and enter the project directory.** Fully extract the 2.0.2 source ZIP, for example to `C:\Tools\FofaMap`. Do not run from a ZIP preview or mistake an outer download directory for the project root. Open the folder containing `pyproject.toml` and `fofamap.py`, type `powershell` in File Explorer’s address bar, and press Enter. Alternatively, use an existing PowerShell window:

```powershell
# Replace this with your actual extracted directory; keep quotes around spaces
Set-Location -LiteralPath 'C:\Tools\FofaMap'
Get-ChildItem pyproject.toml, fofamap.py
```

Both files must be listed. If they are missing, correct the directory before proceeding.

**Step 3: create the environment and install.** These commands directly invoke the environment’s executables, so **activation is unnecessary** and `Activate.ps1` execution-policy errors do not apply. Administrator privileges are normally unnecessary.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\fofamap.exe --version
```

Continue after `FofaMap, version 2.0.2` appears. `Successfully installed` indicates dependency installation succeeded; resolve earlier errors before running business commands. Installing the already published 2.0.1 source still produces 2.0.1.

**Step 4: configure FOFA.** In the same directory, start initialization, select the interface language, and enter your FOFA account and API key when prompted. Plain searches need no model key. Verify FOFA first, then configure a model if required.

```powershell
.\.venv\Scripts\fofamap.exe init
```

Credential storage and model settings follow the [initialization section](../README_EN.md#configure). Keep keys out of screenshots, chats, and example files.

**Step 5: run a first query.** The wizard is the easiest starting point: run the command below, choose ordinary asset search, paste `domain="baidu.com"`, set the page limit to 1, choose configured or smart fields, skip advanced history/export options, and decline Nuclei scanning. Page size follows your preferences; use the command below for an explicit three-record cap. Text entered inside the wizard does not pass through PowerShell’s quote parser.

```powershell
.\.venv\Scripts\fofamap.exe
```

For a copyable command, the following works with **Windows PowerShell 5.1 and PowerShell 7** parsing. `--%` is Windows PowerShell’s stop-parsing token; `\"` passes literal quotes to the executable. **Copy the entire line without line breaks, PowerShell variables, or a trailing pipeline.** See [Microsoft’s argument-parsing documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_parsing).

```powershell
.\.venv\Scripts\fofamap.exe --% -q domain=\"baidu.com\" -f host,ip,port,title --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save
```

This reads FOFA’s index, returns at most three records, and performs no liveness checks or scans. Assess the result table or explicit upstream error; no matches alone do not indicate an installation failure.

**Step 6: start again or upgrade later.** In each new PowerShell window, enter the project directory and run its `.venv\Scripts\` executable. This does not require repeated activation or installation.

```powershell
Set-Location -LiteralPath 'C:\Tools\FofaMap'
.\.venv\Scripts\fofamap.exe --version
.\.venv\Scripts\fofamap.exe
```

After obtaining updated source from the maintainer, repeat Step 3 inside the new project directory. Recreate the environment rather than copying an old `.venv`, whose launchers can retain the previous path. Back up personal configuration and reports before switching source trees.

**Optional: activate for shorter commands.** Run the command below to use `fofamap` directly. A successful activation usually adds `(.venv)` to the prompt; `deactivate` leaves it. If activation is blocked, use the direct executable commands above. FofaMap does not require changing your machine’s execution policy.

```powershell
.\.venv\Scripts\Activate.ps1
fofamap --version
# Leave the environment when finished
deactivate
```

| Symptom | What to do |
|---|---|
| `py` / `python` is not recognized | Reopen PowerShell after installing official Python; check Launcher/PATH installer options. If only `python` works, use it to create `.venv`. |
| `python` opens the Store or reports the wrong version | Check `py -3 --version`, create the environment with an installed runtime, then consistently use `.venv\Scripts\python.exe`. |
| Missing `pyproject.toml` / not a Python project | Enter the source root containing `fofamap.py`; fully extract the ZIP first. |
| Missing `.venv\Scripts\python.exe` | Environment creation failed or the current directory is wrong. Inspect the first command’s error in Step 3. |
| Missing `pip` | Use `.venv\Scripts\python.exe -m pip` rather than a system `pip`; do not create the environment with `--without-pip`. |
| Activation script is blocked | Use the direct executable commands; CLI operation does not depend on activation. |
| Dependency download, proxy, or certificate errors | Check access to PyPI or an organization-approved package source; configure the appropriate proxy or trusted certificates for your environment, then retry. |
| Compiler error / no matching wheel | Upgrade pip inside this `.venv` and check that you use supported 64-bit CPython, rather than its embeddable distribution. |
| Spaces in paths | Use `Set-Location -LiteralPath 'full path'`; invoke a quoted executable with `& 'C:\path with spaces\.venv\Scripts\fofamap.exe' --version`. |
| Query quotes disappear / syntax error | Start with the wizard. For direct execution, copy the `--%` example as one line; Bash quoting is not equivalent across all PowerShell versions. |
| Old version or wrong environment | Run the `.venv\Scripts\fofamap.exe --version` inside the intended source directory; `Get-Command fofamap -All` reveals what a short command resolves to. |
| Garbled Chinese | Use Windows Terminal with a font supporting Chinese; select English in the wizard to distinguish a font/display issue from a functional failure. |
