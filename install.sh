#!/usr/bin/env bash
# FofaMap: isolated Python installation and a user-level command on PATH.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
INDEX_URL="${FOFAMAP_PIP_INDEX_URL:-}"
PYTHON_REQUEST="${FOFAMAP_PYTHON:-3.12}"
ACTION=''
INSTALL_LANGUAGE=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --index-url) INDEX_URL="${2:?missing index URL}"; shift 2 ;;
    --python) PYTHON_REQUEST="${2:?missing Python executable/version}"; shift 2 ;;
    --action) ACTION="${2:?missing action}"; shift 2 ;;
    --language) INSTALL_LANGUAGE="${2:?missing language}"; shift 2 ;;
    --help|-h) printf '%s\n' 'Usage: bash install.sh [--language zh|en] [--action install|repair|uninstall] [--python PATH_OR_VERSION] [--index-url HTTPS_URL]'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
case "$ACTION" in ''|install|repair|uninstall) ;; *) echo 'Action must be install, repair or uninstall.' >&2; exit 2 ;; esac
case "$INSTALL_LANGUAGE" in ''|zh|en) ;; *) echo 'Language must be zh or en.' >&2; exit 2 ;; esac
case "$INDEX_URL" in ''|https://*) ;; *) echo 'The package index must use HTTPS.' >&2; exit 2 ;; esac
[ -z "$INDEX_URL" ] || export PIP_INDEX_URL="$INDEX_URL"
[ -f pyproject.toml ] && [ -f fofamap.py ] || { echo 'Extract the entire source ZIP before installing.' >&2; exit 2; }
source "$ROOT/scripts/install_lifecycle.sh"
fofamap_choose_language
[ "$ACTION" != cancel ] || { echo 'Cancelled / 已取消。'; exit 0; }
fofamap_choose_action
case "$ACTION" in cancel) echo 'Cancelled / 已取消。'; exit 0 ;; uninstall) fofamap_uninstall; exit $? ;; esac
mkdir -p results/install
LOG="$ROOT/results/install/$(date +%Y%m%d-%H%M%S)-unix.log"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; if [ "$rc" -ne 0 ]; then printf "\nInstallation stopped (exit %s). Log: %s\n" "$rc" "$LOG"; fi' EXIT
printf '\nFofaMap installation / %s %s\n' "$(uname -s)" "$(uname -m)"
fofamap_text '[1/6] 查找兼容的 Python（3.10 或以上、64 位）' '[1/6] Finding a compatible Python (3.10 or later, 64-bit)'
compatible() { "$1" -c 'import sys,struct;sys.exit(not((3,10) <= sys.version_info < (3,14) and struct.calcsize("P")==8))' >/dev/null 2>&1; }
PYTHON=''
if [ -f .venv/pyvenv.cfg ] && [ -x .venv/bin/python ] && compatible "$ROOT/.venv/bin/python" && \
  "$ROOT/.venv/bin/python" -c 'import sys;sys.exit(sys.prefix == sys.base_prefix)' >/dev/null 2>&1; then
  PYTHON="$ROOT/.venv/bin/python"
elif [ -e .venv ] || [ -L .venv ]; then
  BACKUP=".venv.backup-$(date +%Y%m%d-%H%M%S)-$$"
  mv .venv "$BACKUP"
  printf 'Preserved incompatible environment: %s\n' "$BACKUP"
fi
if [ -z "$PYTHON" ]; then
  for candidate in "$PYTHON_REQUEST" "python$PYTHON_REQUEST" python3.13 python3.12 python3.11 python3.10 python3 python; do
    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    if [ -n "$resolved" ] && compatible "$resolved"; then PYTHON="$resolved"; break; fi
  done
fi
if [ -n "$PYTHON" ] && [ ! -x .venv/bin/python ]; then
  if ! "$PYTHON" -m venv .venv; then
    [ ! -e .venv ] || mv .venv ".venv.incomplete-$(date +%Y%m%d-%H%M%S)-$$"
    PYTHON=''
  fi
fi
if [ ! -x .venv/bin/python ]; then
  fofamap_text '[2/6] 使用 uv 准备项目独立 Python' '[2/6] Preparing a project-local Python with uv'
  VERSION="$(cat scripts/uv-version.txt)"
  case "$(uname -s)/$(uname -m)" in
    Darwin/arm64) TARGET='aarch64-apple-darwin' ;;
    Darwin/x86_64) TARGET='x86_64-apple-darwin' ;;
    Linux/x86_64) TARGET='x86_64-unknown-linux-musl' ;;
    Linux/aarch64|Linux/arm64) TARGET='aarch64-unknown-linux-musl' ;;
    *) echo 'Supported systems: 64-bit macOS/Linux (x86_64 or ARM64).' >&2; exit 2 ;;
  esac
  TOOL_DIR="$ROOT/.fofamap-tools"
  UV="$TOOL_DIR/uv-$VERSION-$TARGET"
  mkdir -p "$TOOL_DIR"
  printf '%s\n' 'FofaMap managed tools v1' > "$TOOL_DIR/.fofamap-managed"
  if [ ! -x "$UV" ]; then
    ARCHIVE="uv-$TARGET.tar.gz"
    EXPECTED="$(awk -v name="$ARCHIVE" '$2 == name {print $1}' scripts/uv-checksums.txt)"
    [ "${#EXPECTED}" -eq 64 ] || { echo 'Missing uv checksum.' >&2; exit 2; }
    TEMP_DIR="$(mktemp -d "$TOOL_DIR/download.XXXXXXXX")"
    URL="https://github.com/astral-sh/uv/releases/download/$VERSION/$ARCHIVE"
    if command -v curl >/dev/null 2>&1; then curl --fail --location --retry 2 --output "$TEMP_DIR/$ARCHIVE" "$URL"
    elif command -v wget >/dev/null 2>&1; then wget -O "$TEMP_DIR/$ARCHIVE" "$URL"
    else echo 'Install curl or wget and retry.' >&2; exit 2; fi
    if command -v shasum >/dev/null 2>&1; then ACTUAL="$(shasum -a 256 "$TEMP_DIR/$ARCHIVE" | awk '{print $1}')"
    elif command -v sha256sum >/dev/null 2>&1; then ACTUAL="$(sha256sum "$TEMP_DIR/$ARCHIVE" | awk '{print $1}')"
    else echo 'A SHA-256 verifier (shasum/sha256sum) is required.' >&2; exit 2; fi
    [ "$ACTUAL" = "$EXPECTED" ] || { echo 'uv checksum mismatch; download was not executed.' >&2; exit 2; }
    tar -xzf "$TEMP_DIR/$ARCHIVE" -C "$TEMP_DIR"
    cp "$TEMP_DIR/uv-$TARGET/uv" "$UV"
    chmod 755 "$UV"
    rm -rf -- "$TEMP_DIR"
  fi
  export UV_PYTHON_INSTALL_DIR="$TOOL_DIR/python"
  export UV_CACHE_DIR="$TOOL_DIR/cache"
  "$UV" python install --no-bin --no-registry "$PYTHON_REQUEST"
  "$UV" venv --managed-python --python "$PYTHON_REQUEST" "$ROOT/.venv"
else
  fofamap_text '[2/6] 使用项目独立环境' '[2/6] Using the project virtual environment'
fi
PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -c 'import platform,sys;print("Python:",sys.version.split()[0],platform.machine());print("Executable:",sys.executable)'
fofamap_text '[3/6] 更新独立环境中的安装工具' '[3/6] Updating pip inside .venv'
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
  "$PYTHON" -m ensurepip --upgrade
fi
"$PYTHON" -m pip install --upgrade pip "hatchling>=1.27" "editables>=0.5" --only-binary=:all: --disable-pip-version-check --no-input
fofamap_text '[4/6] 安装 FofaMap 与预编译依赖' '[4/6] Installing FofaMap and prebuilt dependencies'
PIP_ARGS=(--no-build-isolation -e "$ROOT" --only-binary=:all: --disable-pip-version-check --no-input)
if [ "$ACTION" = repair ]; then PIP_ARGS+=(--force-reinstall); fi
"$PYTHON" -m pip install "${PIP_ARGS[@]}"
"$PYTHON" scripts/install_language.py --language "$INSTALL_LANGUAGE"
fofamap_text '[5/6] 验证命令行和 MCP（不消耗查询或模型额度）' '[5/6] Verifying CLI and MCP without FOFA/model requests'
"$PYTHON" scripts/check_installation.py
"$PYTHON" scripts/register_command.py
export PATH="$HOME/.local/bin:$PATH"
if [ -t 0 ] && [ -z "${CI:-}" ]; then
  fofamap_text $'\n[6/6] 进入账号与模型配置，请按以下提示操作。' $'\n[6/6] Opening account and model setup. Follow the prompts below.'
  # Password prompts use the terminal directly, outside the installation log.
  if ! "$PYTHON" "$ROOT/fofamap.py" --setup-if-needed </dev/tty >/dev/tty 2>&1; then
    fofamap_text '账号配置尚未完成，运行 fofamap --setup 继续。' 'Account setup is unfinished. Run fofamap --setup to continue.'
  fi
else
  fofamap_text '[6/6] 非交互安装已跳过账号填写；请在终端运行 fofamap --setup。' '[6/6] Noninteractive installation: run fofamap --setup in a terminal to configure accounts and models.'
fi
fofamap_text $'\n安装完成。新开终端输入 fofamap\n账号/模型配置：fofamap --setup' $'\nReady. Open a new terminal and run: fofamap\nAccount/model setup: fofamap --setup'
printf '%s %s\n' "$(fofamap_text '日志：' 'Log:')" "$LOG"
