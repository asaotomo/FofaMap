@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "FOFAMAP_INSTALL_EXIT=%ERRORLEVEL%"
if not defined CI pause
if not "%FOFAMAP_INSTALL_EXIT%"=="0" exit /b %FOFAMAP_INSTALL_EXIT%
if exist "%LOCALAPPDATA%\FofaMap\bin\fofamap.exe" (
  endlocal & set "PATH=%LOCALAPPDATA%\FofaMap\bin;%PATH%" & exit /b 0
)
endlocal & exit /b 0
