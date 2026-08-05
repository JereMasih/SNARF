from snarf.specialists.base import Specialist

INPUT_SCHEMA = {"type": "object", "properties": {"message_limit": {"type": "integer", "description": "Default 100."}}}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "member_count": {"type": "integer"},
        "recent_message_count": {"type": "integer"},
        "active_author_count": {"type": "integer"},
        "error": {"type": "string"},
    },
}


class CommunityPulseSpecialist(Specialist):
    """Métricas reales de la comunidad de Discord del fundador —
    determinístico, sin LLM: contar miembros/mensajes/autores activos reales
    no necesita interpretación (mismo criterio que MonthlyPnLSpecialist).
    Nunca inventa una cifra si Discord no está configurado."""

    name = "community_pulse"
    domain = "community"

    def __init__(self, discord):
        self._discord = discord

    def pulse(self, message_limit: int = 100) -> dict:
        if not self._discord.available:
            return {"error": "Discord no está configurado (falta DISCORD_BOT_TOKEN/DISCORD_GUILD_ID/DISCORD_CHANNEL_ID)."}

        messages = self._discord.list_recent_messages(limit=message_limit)
        member_count = self._discord.guild_member_count()
        active_authors = {m["author"] for m in messages}
        return {
            "member_count": member_count,
            "recent_message_count": len(messages),
            "active_author_count": len(active_authors),
        }

    def handle(self, task: str, context: dict) -> str:
        result = self.pulse(context.get("message_limit", 100))
        if "error" in result:
            return result["error"]
        return (
            f"{result['member_count']} miembros, {result['recent_message_count']} mensajes recientes, "
            f"{result['active_author_count']} autores activos."
        )
