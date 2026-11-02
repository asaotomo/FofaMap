#!/bin/bash
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "$ROOT/install.sh" "$@"
FOFAMAP_INSTALL_EXIT=$?
if [ -t 0 ]; then read -r -p 'Press Enter to close... ' _; fi
exit "$FOFAMAP_INSTALL_EXIT"
