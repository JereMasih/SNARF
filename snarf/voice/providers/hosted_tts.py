from snarf.voice.interface import TTSProvider


class HostedTTSNotConfigured(TTSProvider):
    """Tier 'hosted' — placeholder deliberado, sin proveedor real todavía.

    Principio del diseño: "empezar barato, escalar solo ante evidencia de
    fallo real, nunca por anticipación". Hoy no hay ninguna evidencia de que
    el tier 'local' (Kokoro) no alcance, así que integrar de verdad
    gpt-4o-mini-tts, Cartesia o Inworld ahora sería anticipación, no
    necesidad — y cualquiera de los tres implica una cuenta/API key nueva que
    el fundador todavía no tiene motivo real para crear.

    Este stub existe para que voice/config.yaml pueda declarar el tier 'hosted'
    sin que el router explote, y para que activar un proveedor real el día
    que haga falta de verdad sea agregar una clase acá + una línea de config
    — nunca una refactorización. Ver ADR de la capa de voz.
    """

    name = "hosted_tts_not_configured"

    @property
    def available(self) -> bool:
        return False

    def speak(self, text: str, voice: str | None = None, audio_format: str = "mp3") -> bytes:
        raise RuntimeError(
            "El tier 'hosted' de voz todavía no tiene proveedor real configurado "
            "(gpt-4o-mini-tts / Cartesia / Inworld, a elegir cuando haga falta de "
            "verdad — ver ADR de la capa de voz)."
        )
