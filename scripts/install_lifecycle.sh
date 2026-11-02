#!/usr/bin/env bash
# Sourced by install.sh. Uninstall needs neither Python nor network access.
fofamap_text() {
  if [ "${INSTALL_LANGUAGE:-en}" = zh ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi
}

fofamap_choose_language() {
  local preferred="${FOFAMAP_LANGUAGE:-}" choice default_choice
  if [ -n "$INSTALL_LANGUAGE" ]; then export FOFAMAP_LANGUAGE="$INSTALL_LANGUAGE"; return; fi
  if [ "$preferred" != zh ] && [ "$preferred" != en ] && [ -f "$ROOT/.fofamap-language" ]; then
    IFS= read -r preferred < "$ROOT/.fofamap-language" || true
  fi
  case "$preferred" in zh|en) ;; *)
    case "${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}" in zh*|ZH*) preferred=zh ;; *) preferred=en ;; esac ;;
  esac
  INSTALL_LANGUAGE="$preferred"
  if [ -t 0 ] && [ -z "${CI:-}" ]; then
    if [ "$preferred" = zh ]; then default_choice=1; else default_choice=2; fi
    printf '\n安装语言 / Installation language\n1) 简体中文\n2) English\n0) 取消 / Cancel\n'
    while :; do
      printf '请选择语言 / Choose language [%s]: ' "$default_choice"
      if ! IFS= read -r choice; then ACTION=cancel; return; fi
      case "$choice" in
        '') break ;; 1|zh|ZH) INSTALL_LANGUAGE=zh; break ;; 2|en|EN) INSTALL_LANGUAGE=en; break ;;
        0|q|Q) ACTION=cancel; return ;;
      esac
      printf '请选择 1 或 2 / Please choose 1 or 2.\n'
    done
  fi
  export FOFAMAP_LANGUAGE="$INSTALL_LANGUAGE"
}

fofamap_existing_root() {
  EXISTING_ROOT=''
  if [ -e "$ROOT/.venv" ] || [ -L "$ROOT/.venv" ] || [ -f "$ROOT/.fofamap-install" ]; then
    EXISTING_ROOT="$ROOT"
  elif [ -f "$HOME/.local/bin/.fofamap-install" ]; then
    local magic recorded
    { IFS= read -r magic; IFS= read -r recorded; } < "$HOME/.local/bin/.fofamap-install" || true
    if [ "$magic" = 'FofaMap managed installation v1' ] && [ -f "$recorded/fofamap.py" ]; then
      EXISTING_ROOT="$recorded"
    fi
  elif [ -L "$HOME/.local/bin/fofamap" ]; then
    local linked
    linked="$(readlink "$HOME/.local/bin/fofamap")"
    case "$linked" in
      */.venv/bin/fofamap)
        linked="${linked%/.venv/bin/fofamap}"
        [ ! -f "$linked/fofamap.py" ] || EXISTING_ROOT="$linked" ;;
    esac
  fi
}

fofamap_choose_action() {
  fofamap_existing_root
  fofamap_text 'FofaMap 安装管理' 'FofaMap installation manager'
  if [ -n "$EXISTING_ROOT" ]; then printf '%s %s\n' "$(fofamap_text '已有安装：' 'Existing installation:')" "$EXISTING_ROOT"; fi
  if [ -n "$ACTION" ]; then return; fi
  if [ ! -t 0 ] || [ -n "${CI:-}" ]; then
    if [ -n "$EXISTING_ROOT" ]; then ACTION=repair; else ACTION=install; fi
    printf '%s %s\n' "$(fofamap_text '非交互操作（可用 --action 指定）：' 'Noninteractive action (override with --action):')" "$ACTION"
    return
  fi
  while :; do
    if [ -n "$EXISTING_ROOT" ]; then
      fofamap_text $'1) 修复安装\n2) 卸载（保留配置和报告）\n0) 取消' $'1) Repair installation\n2) Uninstall (keep settings and reports)\n0) Cancel'
    else
      fofamap_text $'1) 安装\n0) 取消' $'1) Install\n0) Cancel'
    fi
    printf '%s ' "$(fofamap_text '请选择操作 [1]:' 'Choose action [1]:')"
    local choice
    if ! IFS= read -r choice; then ACTION=cancel; return; fi
    case "$choice" in
      ''|1) if [ -n "$EXISTING_ROOT" ]; then ACTION=repair; else ACTION=install; fi; return ;;
      2) if [ -n "$EXISTING_ROOT" ]; then ACTION=uninstall; return; fi ;;
      0|q|Q) ACTION=cancel; return ;;
    esac
    fofamap_text '请输入菜单中的选项。' 'Please choose a listed option.'
  done
}

fofamap_remove_profile_block() {
  local profile="$1" temporary
  [ -f "$profile" ] || return 0
  # Reject malformed blocks; never discard user text following an unmatched marker.
  temporary="$(mktemp "${profile}.fofamap.XXXXXXXX")"
  if awk '
    $0 == "# >>> FofaMap command >>>" { if (inside) bad=1; inside=1; next }
    $0 == "# <<< FofaMap command <<<" { if (!inside) bad=1; inside=0; next }
    !inside { print }
    END { if (inside || bad) exit 1 }
  ' "$profile" > "$temporary"; then
    if ! cmp -s "$profile" "$temporary"; then cat "$temporary" > "$profile"; fi
  else
    printf 'Kept malformed PATH block for manual review: %s\n' "$profile"
  fi
  rm -f -- "$temporary"
}

fofamap_uninstall() {
  local target_root="${EXISTING_ROOT:-$ROOT}" bin_dir="$HOME/.local/bin" marker magic recorded checksum linked owned=no actual
  [ -f "$target_root/fofamap.py" ] && [ -f "$target_root/pyproject.toml" ] || { echo 'Cannot verify installation directory.' >&2; return 1; }
  target_root="$(cd -- "$target_root" && pwd -P)"
  printf '\nUninstall / 卸载: %s\n' "$target_root"
  marker="$bin_dir/.fofamap-install"
  recorded='' checksum=''
  if [ -f "$marker" ]; then
    { IFS= read -r magic; IFS= read -r recorded; IFS= read -r checksum; } < "$marker" || true
    [ "$magic" = 'FofaMap managed installation v1' ] || recorded=''
  fi
  if [ -L "$bin_dir/fofamap" ]; then
    linked="$(readlink "$bin_dir/fofamap")"
    [ "$linked" != "$target_root/.venv/bin/fofamap" ] || owned=yes
  elif [ "$recorded" = "$target_root" ]; then
    if [ ! -e "$bin_dir/fofamap" ]; then owned=yes
    elif [ -f "$bin_dir/fofamap" ] && [ "${#checksum}" -eq 64 ]; then
      actual=''
      if command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$bin_dir/fofamap" | awk '{print $1}')"
      elif command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$bin_dir/fofamap" | awk '{print $1}')"; fi
      [ "$actual" != "$checksum" ] || owned=yes
    fi
  fi
  if [ "$owned" = yes ]; then
    rm -f -- "$bin_dir/fofamap"
    if [ "$recorded" = "$target_root" ]; then rm -f -- "$marker"; fi
    local profile
    for profile in .profile .bashrc .zshrc .zprofile .bash_profile .bash_login .config/fish/config.fish; do
      fofamap_remove_profile_block "$HOME/$profile"
    done
    echo 'Removed this installation command and managed shell PATH blocks.'
  else
    echo 'Kept command/PATH belonging to another installation or modified by the user.'
  fi
  if [ -L "$target_root/.venv" ]; then
    echo 'Kept externally linked .venv; remove that link manually if no longer needed.'
  elif [ -d "$target_root/.venv" ]; then
    if [ -f "$target_root/.venv/pyvenv.cfg" ] || [ -f "$target_root/.fofamap-install" ]; then
      rm -rf -- "$target_root/.venv"
    else echo 'Kept unrecognized .venv directory.'; fi
  fi
  if [ ! -L "$target_root/.fofamap-tools" ] && [ -f "$target_root/.fofamap-tools/.fofamap-managed" ]; then
    rm -rf -- "$target_root/.fofamap-tools"
  elif [ -e "$target_root/.fofamap-tools" ]; then
    echo 'Kept unmarked or externally linked tools directory.'
  fi
  rm -f -- "$target_root/.fofamap-install"
  echo 'Uninstalled. Source, settings, keys, results, reports and backups are preserved.'
  echo '卸载完成，源码、账号配置、密钥、查询结果、报告及备份均保留。重新运行安装脚本即可安装。'
  echo 'Reopen your terminal to refresh PATH / 重新打开终端使 PATH 生效。'
}
