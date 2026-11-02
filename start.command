#!/bin/bash
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "$ROOT/start.sh" "$@"
FOFAMAP_START_EXIT=$?
if [ "$FOFAMAP_START_EXIT" -ne 0 ] && [ -t 0 ]; then read -r -p 'Press Enter to close... ' _; fi
exit "$FOFAMAP_START_EXIT"
