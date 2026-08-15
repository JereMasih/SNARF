#!/bin/zsh
# Prende la pila real de Snarf (la misma que estaba corriendo antes de desactivar
# el autoarranque): server 8002, mlx-fast + su watchdog, kokoro-tts y n8n (Colima+Docker).
# mlx-heavy/mlx-mid quedan afuera: sus .plist existen pero no estaban en uso; se pueden
# cargar a mano con "launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.snarf.mlx-<heavy|mid>.plist"
# si hace falta.
set -uo pipefail

UID_NUM=$(id -u)
LABELS=(
  com.snarf.server
  com.snarf.mlx-fast
  com.snarf.mlx-watchdog
  com.snarf.kokoro-tts
  com.snarf.n8n
)

for label in "${LABELS[@]}"; do
  launchctl bootstrap "gui/${UID_NUM}" "$HOME/Library/LaunchAgents/${label}.plist" 2>/dev/null
  echo "iniciado: ${label}"
done

echo "Snarf: todo prendido (server 8002, mlx-fast, kokoro-tts, n8n)."
osascript -e 'display notification "Todo prendido" with title "Snarf"' 2>/dev/null || true
