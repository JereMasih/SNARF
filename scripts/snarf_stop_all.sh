#!/bin/zsh
# Apaga todo lo que Snarf puede tener corriendo: los LaunchAgents y, aparte,
# Colima+Docker (el job com.snarf.n8n solo dispara "colima start && docker compose up -d"
# y termina, así que su contenedor sigue vivo aunque el job ya no esté cargado).
set -uo pipefail

UID_NUM=$(id -u)
LABELS=(
  com.snarf.server
  com.snarf.mlx-fast
  com.snarf.mlx-heavy
  com.snarf.mlx-mid
  com.snarf.mlx-watchdog
  com.snarf.kokoro-tts
  com.snarf.n8n
)

for label in "${LABELS[@]}"; do
  if launchctl print "gui/${UID_NUM}/${label}" >/dev/null 2>&1; then
    launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null
    echo "detenido: ${label}"
  fi
done

REPO="/Users/jeremiasabdelmasih/Documents/PROGRAMACION/PROYECTOS/SNARF"
/opt/homebrew/bin/docker compose -f "${REPO}/docker-compose.n8n.yml" down 2>/dev/null
/opt/homebrew/bin/colima stop 2>/dev/null

echo "Snarf: todo apagado."
osascript -e 'display notification "Todo apagado" with title "Snarf"' 2>/dev/null || true
