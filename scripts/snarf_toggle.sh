#!/bin/zsh
# Un solo interruptor: si el server de Snarf está corriendo, apaga todo; si no, prende todo.
DIR="$(cd "$(dirname "$0")" && pwd)"

if launchctl print "gui/$(id -u)/com.snarf.server" >/dev/null 2>&1; then
  "${DIR}/snarf_stop_all.sh"
else
  "${DIR}/snarf_start_all.sh"
fi
