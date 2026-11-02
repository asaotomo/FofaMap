# Sourced by install.ps1. Offline uninstall also works when Python is damaged.
function Get-FofaMapText([string]$Zh, [string]$En) {
    if ($Language -eq 'zh') { return $Zh }
    return $En
}

function Select-FofaMapLanguage([bool]$Interactive = (-not $env:CI -and -not [Console]::IsInputRedirected)) {
    if ($Language) { return $Language }
    $Preferred = $env:FOFAMAP_LANGUAGE
    $Marker = Join-Path $Root '.fofamap-language'
    if ($Preferred -notin @('zh','en') -and (Test-Path -LiteralPath $Marker -PathType Leaf)) {
        $Preferred = [IO.File]::ReadAllText($Marker).Trim()
    }
    if ($Preferred -notin @('zh','en')) {
        $Preferred = if ([Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'zh') { 'zh' } else { 'en' }
    }
    if (-not $Interactive) { return $Preferred }
    $Default = if ($Preferred -eq 'zh') { '1' } else { '2' }
    Write-Host "`n安装语言 / Installation language" -ForegroundColor Cyan
    Write-Host '1) 简体中文'
    Write-Host '2) English'
    Write-Host '0) 取消 / Cancel'
    while ($true) {
        $Choice = Read-Host "请选择语言 / Choose language [$Default]"
        if ($null -eq $Choice) { return '' }
        switch ($Choice.Trim()) {
            '' { return $Preferred }
            { $_ -in @('1','zh','ZH') } { return 'zh' }
            { $_ -in @('2','en','EN') } { return 'en' }
            { $_ -in @('0','q','Q') } { return '' }
        }
        Write-Host '请选择 1 或 2 / Please choose 1 or 2.'
    }
}

function Get-FofaMapExistingRoot {
    if ((Test-Path -LiteralPath (Join-Path $Root '.venv')) -or (Test-Path -LiteralPath (Join-Path $Root '.fofamap-install'))) { return $Root }
    $Bin = Join-Path $env:LOCALAPPDATA 'FofaMap\bin'
    $Marker = Join-Path $Bin '.fofamap-install'
    if (Test-Path -LiteralPath $Marker -PathType Leaf) {
        $Lines = [IO.File]::ReadAllLines($Marker)
        if ($Lines.Length -ge 2 -and $Lines[0] -eq 'FofaMap managed installation v1' -and (Test-Path -LiteralPath (Join-Path $Lines[1] 'fofamap.py'))) { return $Lines[1] }
    }
    # Earlier installers copied pip's launcher without an ownership record.
    $Entry = Join-Path $Bin 'fofamap.exe'
    if (Test-Path -LiteralPath $Entry -PathType Leaf) {
        $Bytes = [IO.File]::ReadAllBytes($Entry)
        $Match = [regex]::Match([Text.Encoding]::UTF8.GetString($Bytes), '#!"?([^\r\n"]+\\\.venv\\Scripts\\python(?:w)?\.exe)"?\r?\n')
        if ($Match.Success) {
            $LegacyRoot = Split-Path (Split-Path (Split-Path $Match.Groups[1].Value -Parent) -Parent) -Parent
            if (Test-Path -LiteralPath (Join-Path $LegacyRoot 'fofamap.py')) { return $LegacyRoot }
        }
    }
    return ''
}

function Select-FofaMapAction([bool]$Interactive = (-not $env:CI -and -not [Console]::IsInputRedirected)) {
    Write-Host (Get-FofaMapText "`nFofaMap 安装管理" "`nFofaMap installation manager") -ForegroundColor Cyan
    if ($ExistingRoot) { Write-Host ((Get-FofaMapText '已有安装：' 'Existing installation: ') + $ExistingRoot) }
    if ($Action) { return $Action }
    if (-not $Interactive) {
        $Selected = if ($ExistingRoot) { 'repair' } else { 'install' }
        Write-Host ((Get-FofaMapText '非交互操作（可用 -Action 指定）：' 'Noninteractive action (override with -Action): ') + $Selected)
        return $Selected
    }
    while ($true) {
        if ($ExistingRoot) {
            Write-Host (Get-FofaMapText '1) 修复安装' '1) Repair installation')
            Write-Host (Get-FofaMapText '2) 卸载（保留配置和报告）' '2) Uninstall (keep settings and reports)')
        } else { Write-Host (Get-FofaMapText '1) 安装' '1) Install') }
        Write-Host (Get-FofaMapText '0) 取消' '0) Cancel')
        $Choice = Read-Host (Get-FofaMapText '请选择操作 [1]' 'Choose action [1]')
        if ($null -eq $Choice) { return 'cancel' }
        switch ($Choice.Trim()) {
            { $_ -in @('', '1') } { if ($ExistingRoot) { return 'repair' } else { return 'install' } }
            '2' { if ($ExistingRoot) { return 'uninstall' } }
            { $_ -in @('0', 'q', 'Q') } { return 'cancel' }
        }
        Write-Host (Get-FofaMapText '请输入菜单中的选项。' 'Please choose a listed option.')
    }
}

function Remove-FofaMapPath([string]$Bin) {
    $Key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    if ($Key) {
        try {
            $Existing = $Key.GetValue('Path', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            if ($null -ne $Existing) {
                $Kind = $Key.GetValueKind('Path')
                $Entries = @($Existing -split ';' | Where-Object {
                    [Environment]::ExpandEnvironmentVariables($_.Trim().Trim('"')).Replace('/', '\').TrimEnd('\') -ine $Bin.TrimEnd('\')
                })
                $Key.SetValue('Path', ($Entries -join ';'), $Kind)
            }
        } finally { $Key.Dispose() }
    }
    $env:Path = (@($env:Path -split ';' | Where-Object { $_.TrimEnd('\') -ine $Bin.TrimEnd('\') }) -join ';')
    if (-not ('FofaMapInstallEnvironment' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FofaMapInstallEnvironment {
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint msg, UIntPtr wparam, string lparam, uint flags, uint timeout, out UIntPtr result);
}
'@
    }
    $Result = [UIntPtr]::Zero
    [void][FofaMapInstallEnvironment]::SendMessageTimeout([IntPtr]0xffff, 0x001a, [UIntPtr]::Zero, 'Environment', 2, 3000, [ref]$Result)
}

function Uninstall-FofaMap {
    $TargetRoot = if ($ExistingRoot) { $ExistingRoot } else { $Root }
    if (-not (Test-Path -LiteralPath (Join-Path $TargetRoot 'fofamap.py')) -or -not (Test-Path -LiteralPath (Join-Path $TargetRoot 'pyproject.toml'))) { throw 'Cannot verify installation directory.' }
    $TargetRoot = [IO.Path]::GetFullPath($TargetRoot).TrimEnd('\')
    Write-Host "`nUninstall: $TargetRoot" -ForegroundColor Cyan
    $Bin = Join-Path $env:LOCALAPPDATA 'FofaMap\bin'
    $Entry = Join-Path $Bin 'fofamap.exe'
    $Marker = Join-Path $Bin '.fofamap-install'
    $RecordRoot = ''
    $Checksum = ''
    if (Test-Path -LiteralPath $Marker -PathType Leaf) {
        $Lines = [IO.File]::ReadAllLines($Marker)
        if ($Lines.Length -ge 3 -and $Lines[0] -eq 'FofaMap managed installation v1') { $RecordRoot = $Lines[1]; $Checksum = $Lines[2] }
    }
    $Owned = $false
    if ($RecordRoot -ieq $TargetRoot) {
        $Owned = -not (Test-Path -LiteralPath $Entry)
        if (-not $Owned -and $Checksum -match '^[a-f0-9]{64}$') { $Owned = (Get-FileHash -LiteralPath $Entry -Algorithm SHA256).Hash -ieq $Checksum }
    } elseif (-not $RecordRoot -and (Test-Path -LiteralPath $Entry -PathType Leaf)) {
        $SourceEntry = Join-Path $TargetRoot '.venv\Scripts\fofamap.exe'
        if (Test-Path -LiteralPath $SourceEntry -PathType Leaf) { $Owned = (Get-FileHash -LiteralPath $Entry -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $SourceEntry -Algorithm SHA256).Hash }
    }
    if ($Owned) {
        if (Test-Path -LiteralPath $Entry) { Remove-Item -LiteralPath $Entry -Force }
        if (Test-Path -LiteralPath $Marker) { Remove-Item -LiteralPath $Marker -Force }
        # The directory is dedicated to FofaMap, but keep its PATH if the user added other commands.
        $OtherFiles = @(Get-ChildItem -LiteralPath $Bin -Force -ErrorAction SilentlyContinue)
        if ($OtherFiles.Count -eq 0) {
            Remove-FofaMapPath $Bin
            Remove-Item -LiteralPath $Bin -Force
        } else { Write-Host 'Kept command directory/PATH because it contains other user files.' }
        Write-Host 'Removed this installation command.'
    } else { Write-Host 'Kept command/PATH belonging to another installation or modified by the user.' }
    $Venv = Join-Path $TargetRoot '.venv'
    if (Test-Path -LiteralPath $Venv) {
        $Info = Get-Item -LiteralPath $Venv -Force
        if ($Info.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Write-Host 'Kept externally linked .venv; remove that link manually if no longer needed.'
        } elseif ((Test-Path -LiteralPath (Join-Path $Venv 'pyvenv.cfg')) -or (Test-Path -LiteralPath (Join-Path $TargetRoot '.fofamap-install'))) {
            Remove-Item -LiteralPath $Venv -Recurse -Force
        } else { Write-Host 'Kept unrecognized .venv directory.' }
    }
    $Tools = Join-Path $TargetRoot '.fofamap-tools'
    if (Test-Path -LiteralPath $Tools) {
        $Info = Get-Item -LiteralPath $Tools -Force
        if (-not ($Info.Attributes -band [IO.FileAttributes]::ReparsePoint) -and (Test-Path -LiteralPath (Join-Path $Tools '.fofamap-managed'))) {
            Remove-Item -LiteralPath $Tools -Recurse -Force
        } else { Write-Host 'Kept unmarked or externally linked tools directory.' }
    }
    $RootMarker = Join-Path $TargetRoot '.fofamap-install'
    if (Test-Path -LiteralPath $RootMarker) { Remove-Item -LiteralPath $RootMarker -Force }
    Write-Host 'Uninstalled. Source, settings, keys, results, reports and backups are preserved.' -ForegroundColor Green
    Write-Host 'Rerun the installer to install again. Reopen your terminal to refresh PATH.'
}
