# FofaMap Windows installer. Isolated Python and user-level PATH; no admin needed.
[CmdletBinding()]
param(
    [string]$IndexUrl = $(if ($env:FOFAMAP_PIP_INDEX_URL) { $env:FOFAMAP_PIP_INDEX_URL } else { '' }),
    [string]$Python = '',
    [ValidateSet('install','repair','uninstall')][string]$Action = '',
    [ValidateSet('zh','en')][string]$Language = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = $PSScriptRoot
Set-Location -LiteralPath $Root
if ($IndexUrl -and -not $IndexUrl.StartsWith('https://')) { throw 'The package index must use HTTPS.' }
if ($IndexUrl) { $env:PIP_INDEX_URL = $IndexUrl }
if (-not (Test-Path 'pyproject.toml') -or -not (Test-Path 'fofamap.py')) { throw 'Extract the entire source ZIP before installing.' }
. (Join-Path $Root 'scripts\install_lifecycle.ps1')
$Language = Select-FofaMapLanguage
if (-not $Language) { Write-Host '已取消 / Cancelled.'; exit 0 }
$env:FOFAMAP_LANGUAGE = $Language
$ExistingRoot = Get-FofaMapExistingRoot
$Action = Select-FofaMapAction
if ($Action -eq 'cancel') { Write-Host 'Cancelled.'; exit 0 }
if ($Action -eq 'uninstall') {
    try { Uninstall-FofaMap; exit 0 }
    catch { Write-Host "Uninstall stopped: $($_.Exception.Message). Close running FofaMap tasks and retry." -ForegroundColor Red; exit 1 }
}
$LogDir = Join-Path $Root 'results\install'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-windows.log')
$Transcript = $false
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $Program" }
}
function Test-Python([string]$Program) {
    if ($Program -match '\\WindowsApps\\') { return $false }
    if (-not $Program -or -not (Test-Path -LiteralPath $Program -PathType Leaf)) { return $false }
    try {
        $Probe = & $Program -c "import sys,sysconfig,struct;print('FOFAMAP_PY_OK' if (3,10) <= sys.version_info < (3,14) and struct.calcsize('P')==8 and sysconfig.get_platform().lower()=='win-amd64' else 'INCOMPATIBLE')" 2>$null
        return ($LASTEXITCODE -eq 0 -and ($Probe -contains 'FOFAMAP_PY_OK'))
    } catch { return $false }
}
function Test-Venv([string]$Program) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root '.venv\pyvenv.cfg')) -or -not (Test-Python $Program)) { return $false }
    try {
        $Probe = & $Program -c "import sys;print('FOFAMAP_VENV_OK' if sys.prefix != sys.base_prefix else 'NOT_ISOLATED')" 2>$null
        return ($LASTEXITCODE -eq 0 -and ($Probe -contains 'FOFAMAP_VENV_OK'))
    } catch { return $false }
}
try {
    Start-Transcript -Path $Log -Force | Out-Null
    $Transcript = $true
    Write-Host "`nFofaMap installation / Windows"
    Write-Host (Get-FofaMapText '[1/6] 查找兼容的 x64 Python（3.10 或以上）' '[1/6] Finding a compatible x64 Python (3.10 or later)')
    $VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
    $Compatible = Test-Venv $VenvPython
    if (-not $Compatible -and (Test-Path -LiteralPath (Join-Path $Root '.venv'))) {
        $Backup = '.venv.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID
        Move-Item -LiteralPath (Join-Path $Root '.venv') -Destination (Join-Path $Root $Backup)
        Write-Host "Preserved incompatible/ARM64 environment: $Backup"
    }
    if (-not $Compatible) {
        $Candidates = @()
        if ($Python) { $Candidates += $Python }
        foreach ($Name in @('python3.exe','python.exe')) {
            $Command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue
            if ($Command) { $Candidates += $Command.Source }
        }
        foreach ($Base in @("$env:LOCALAPPDATA\Programs\Python", "$env:APPDATA\uv\python")) {
            if (Test-Path -LiteralPath $Base) {
                $Candidates += @(Get-ChildItem -LiteralPath $Base -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'python.exe' })
            }
        }
        $Selected = $null
        foreach ($Candidate in $Candidates) {
            if (Test-Python $Candidate) { $Selected = $Candidate; break }
        }
        if ($Selected) {
            Invoke-Checked $Selected @('-m','venv',(Join-Path $Root '.venv'))
        } else {
            Write-Host '[2/6] Preparing project-local x64 Python (also for Windows 11 on ARM)'
            $Version = (Get-Content -LiteralPath 'scripts\uv-version.txt' -Raw).Trim()
            $Archive = 'uv-x86_64-pc-windows-msvc.zip'
            $ToolDir = Join-Path $Root '.fofamap-tools'
            $Uv = Join-Path $ToolDir "uv-$Version-x64.exe"
            New-Item -ItemType Directory -Force -Path $ToolDir | Out-Null
            [IO.File]::WriteAllText((Join-Path $ToolDir '.fofamap-managed'), 'FofaMap managed tools v1')
            if (-not (Test-Path -LiteralPath $Uv)) {
                $ChecksumLine = Get-Content -LiteralPath 'scripts\uv-checksums.txt' | Where-Object { $_ -match ([regex]::Escape($Archive) + '$') } | Select-Object -First 1
                if (-not $ChecksumLine) { throw 'Missing uv checksum.' }
                $Expected = ($ChecksumLine -split '\s+')[0]
                $TempDir = Join-Path $ToolDir ('download-' + [guid]::NewGuid().ToString('N'))
                New-Item -ItemType Directory -Path $TempDir | Out-Null
                $Zip = Join-Path $TempDir $Archive
                Write-Host "Downloading uv $Version (SHA-256 will be verified)"
                Invoke-WebRequest -TimeoutSec 120 -UseBasicParsing -Uri "https://github.com/astral-sh/uv/releases/download/$Version/$Archive" -OutFile $Zip
                $Actual = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($Expected.Length -ne 64 -or $Actual -ne $Expected) { throw 'uv checksum mismatch; download was not executed.' }
                Expand-Archive -LiteralPath $Zip -DestinationPath $TempDir
                $Binary = Get-ChildItem -LiteralPath $TempDir -Recurse -Filter 'uv.exe' | Select-Object -First 1
                if (-not $Binary) { throw 'uv.exe missing from verified archive.' }
                Copy-Item -LiteralPath $Binary.FullName -Destination $Uv
                Remove-Item -LiteralPath $TempDir -Recurse -Force
            }
            $env:UV_PYTHON_INSTALL_DIR = Join-Path $ToolDir 'python'
            $env:UV_CACHE_DIR = Join-Path $ToolDir 'cache'
            $Request = 'cpython-3.12-windows-x86_64-none'
            Invoke-Checked $Uv @('python','install','--no-bin','--no-registry',$Request)
            Invoke-Checked $Uv @('venv','--managed-python','--python',$Request,(Join-Path $Root '.venv'))
        }
    }
    if (-not (Test-Venv $VenvPython)) { throw 'An isolated x64 Python environment is required. On ARM hardware use Windows 11 with x64 app emulation.' }
    Write-Host (Get-FofaMapText '[2/6] 项目独立环境已就绪' '[2/6] Project virtual environment ready')
    Invoke-Checked $VenvPython @('-c',"import sysconfig,sys;print('Python:',sys.version.split()[0],sysconfig.get_platform());print('Executable:',sys.executable)")
    Write-Host (Get-FofaMapText '[3/6] 更新独立环境中的安装工具' '[3/6] Updating pip inside .venv')
    $HasPip = $false
    try {
        & $VenvPython -m pip --version 2>$null | Out-Null
        $HasPip = ($LASTEXITCODE -eq 0)
    } catch { $HasPip = $false }
    if (-not $HasPip) { Invoke-Checked $VenvPython @('-m','ensurepip','--upgrade') }
    Invoke-Checked $VenvPython @('-m','pip','install','--upgrade','pip','hatchling>=1.27','editables>=0.5','--only-binary=:all:','--disable-pip-version-check','--no-input')
    Write-Host (Get-FofaMapText '[4/6] 安装 FofaMap 与预编译依赖' '[4/6] Installing FofaMap and prebuilt dependencies')
    $PipArguments = @('-m','pip','install','--no-build-isolation','-e',$Root,'--only-binary=:all:','--disable-pip-version-check','--no-input')
    if ($Action -eq 'repair') { $PipArguments += '--force-reinstall' }
    Invoke-Checked $VenvPython $PipArguments
    Invoke-Checked $VenvPython @((Join-Path $Root 'scripts\install_language.py'),'--language',$Language)
    Write-Host (Get-FofaMapText '[5/6] 验证命令行和 MCP（不消耗查询或模型额度）' '[5/6] Verifying CLI and MCP without FOFA/model requests')
    Invoke-Checked $VenvPython @((Join-Path $Root 'scripts\check_installation.py'))
    Invoke-Checked $VenvPython @((Join-Path $Root 'scripts\register_command.py'))
    $CommandDir = Join-Path $env:LOCALAPPDATA 'FofaMap\bin'
    $env:Path = $CommandDir + ';' + $env:Path
    if ($Transcript) { Stop-Transcript | Out-Null; $Transcript = $false }
    if (-not $env:CI) {
        Write-Host (Get-FofaMapText "`n[6/6] 进入账号与模型配置，请按以下提示操作。" "`n[6/6] Opening account and model setup. Follow the prompts below.") -ForegroundColor Cyan
        & $VenvPython (Join-Path $Root 'fofamap.py') --setup-if-needed
        if ($LASTEXITCODE -ne 0) { Write-Host (Get-FofaMapText '账号配置尚未完成，运行 fofamap --setup 继续。' 'Account setup is unfinished. Run fofamap --setup to continue.') }
    } else {
        Write-Host (Get-FofaMapText '[6/6] 非交互安装已跳过账号填写；请在终端运行 fofamap --setup。' '[6/6] CI installation: interactive setup skipped. Run fofamap --setup in a terminal.')
    }
    Write-Host (Get-FofaMapText "`n安装完成。输入 fofamap 打开，或 fofamap --setup 配置账号和模型。" "`nReady. Run fofamap to open, or fofamap --setup to configure accounts and models.")
    Write-Host "Log: $Log"
} catch {
    Write-Host "`nInstallation stopped: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log: $Log"
    exit 1
} finally {
    if ($Transcript) { Stop-Transcript | Out-Null }
}
