@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Run install.bat first.
  if not defined CI pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0fofamap.py" %*
set "FOFAMAP_START_EXIT=%ERRORLEVEL%"
if not defined CI pause
exit /b %FOFAMAP_START_EXIT%
