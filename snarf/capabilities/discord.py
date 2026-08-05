"""Discord real (Fase I, rama Community — ver plan de expansión
"Inteligencia Ejecutiva"). Vendor decidido en el plan. Bot token real vía
`DISCORD_BOT_TOKEN`, mismo patrón lazy-client-desde-env-var que el resto de
las Capacidades de este repo (ver Notion/Tavily). Servidor/canal reales vía
`DISCORD_GUILD_ID`/`DISCORD_CHANNEL_ID` — sin esos tres, `available` es
`False` y ningún método real se llama."""

import os

import requests

from snarf.capabilities.base import Capability

API_BASE = "https://discord.com/api/v10"
REQUEST_TIMEOUT_SECONDS = 20


class Discord(Capability):
    name = "discord"

    def __init__(self):
        self._bot_token = os.environ.get("DISCORD_BOT_TOKEN")
        self.guild_id = os.environ.get("DISCORD_GUILD_ID")
        self.channel_id = os.environ.get("DISCORD_CHANNEL_ID")

    @property
    def available(self) -> bool:
        return bool(self._bot_token and self.guild_id and self.channel_id)

    def _headers(self) -> dict:
        return {"Authorization": f"Bot {self._bot_token}", "Content-Type": "application/json"}

    def _require_available(self) -> None:
        if not self.available:
            raise RuntimeError(
                "Discord no está configurado (DISCORD_BOT_TOKEN/DISCORD_GUILD_ID/DISCORD_CHANNEL_ID). "
                "Ver .env.example."
            )

    def send_message(self, content: str, channel_id: str | None = None) -> dict:
        self._require_available()
        target = channel_id or self.channel_id
        response = requests.post(
            f"{API_BASE}/channels/{target}/messages", headers=self._headers(), json={"content": content},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return {"id": data.get("id"), "channel_id": target, "content": content}

    def list_recent_messages(self, channel_id: str | None = None, limit: int = 50) -> list[dict]:
        self._require_available()
        target = channel_id or self.channel_id
        response = requests.get(
            f"{API_BASE}/channels/{target}/messages", headers=self._headers(), params={"limit": limit},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return [
            {
                "id": m["id"],
                "author": m.get("author", {}).get("username", ""),
                "content": m.get("content", ""),
                "timestamp": m.get("timestamp", ""),
            }
            for m in response.json()
        ]

    def guild_member_count(self, guild_id: str | None = None) -> int:
        self._require_available()
        target = guild_id or self.guild_id
        response = requests.get(
            f"{API_BASE}/guilds/{target}", headers=self._headers(), params={"with_counts": "true"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json().get("approximate_member_count", 0)
