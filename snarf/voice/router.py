from pathlib import Path

import yaml

from snarf.voice.providers.elevenlabs_tts import ElevenLabsTTSProvider
from snarf.voice.providers.groq_stt import GroqSTT
from snarf.voice.providers.hosted_tts import HostedTTSNotConfigured
from snarf.voice.providers.kokoro_tts import KokoroTTS
from snarf.voice.providers.local_stt import LocalWhisperSTT

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"

STT_PROVIDERS = {"groq": GroqSTT, "local_whisper": LocalWhisperSTT}
TTS_PROVIDERS = {
    "kokoro": KokoroTTS,
    "elevenlabs_premium": ElevenLabsTTSProvider,
    "hosted_not_configured": HostedTTSNotConfigured,
}
# Qué sección de config.yaml pasa como kwargs al construir cada proveedor
# (solo los que de verdad necesitan configuración propia, ej. Kokoro con su
# base_url — así voice/config.yaml queda como única fuente de verdad en vez
# de env vars sueltas).
PROVIDER_CONFIG_SECTION = {"kokoro": "kokoro"}


class TierUnavailable(RuntimeError):
    """El tier de voz pedido no está disponible ahora mismo.

    Regla dura del diseño: "si el tier local está caído, Snarf avisa y
    pregunta antes de gastar en hosted — nunca escala de tier en silencio".
    Este error es esa señal: quien llama a VoiceRouter.speak() decide qué
    mostrarle al fundador, el router nunca decide gastar plata por su cuenta.
    """


class VoiceRouter:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self._config = self._load_config(config_path)
        self._stt_cache: dict[str, object] = {}
        self._tts_cache: dict[str, object] = {}

    @staticmethod
    def _load_config(path: Path) -> dict:
        if not path.exists():
            raise RuntimeError(f"voice/config.yaml no encontrado en {path}")
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _stt(self, name: str):
        if name not in self._stt_cache:
            self._stt_cache[name] = STT_PROVIDERS[name]()
        return self._stt_cache[name]

    def _tts(self, name: str):
        if name not in self._tts_cache:
            cls = TTS_PROVIDERS[name]
            section = PROVIDER_CONFIG_SECTION.get(name)
            kwargs = self._config.get(section, {}) if section else {}
            self._tts_cache[name] = cls(**kwargs)
        return self._tts_cache[name]

    @property
    def stt_available(self) -> bool:
        primary = self._stt(self._config["stt"]["primary"])
        if primary.available:
            return True
        fallback_name = self._config["stt"].get("fallback")
        return bool(fallback_name and self._stt(fallback_name).available)

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcribe con el proveedor primario; degrada al fallback local sin
        preguntar (costo cero, así que no aplica la regla de "nunca escalar en
        silencio" — esa regla es sobre gastar plata de más, no sobre usar algo
        gratis que ya está configurado)."""
        stt_config = self._config["stt"]
        primary_name = stt_config["primary"]
        fallback_name = stt_config.get("fallback")
        primary = self._stt(primary_name)

        if primary.available:
            try:
                return primary.transcribe(audio_bytes, filename=filename)
            except Exception as exc:
                fallback = self._stt(fallback_name) if fallback_name else None
                if not fallback or not fallback.available:
                    raise
                print(f"[voice.router] {primary_name} falló ({exc}), degradando a {fallback_name}")
                return fallback.transcribe(audio_bytes, filename=filename)

        fallback = self._stt(fallback_name) if fallback_name else None
        if fallback and fallback.available:
            return fallback.transcribe(audio_bytes, filename=filename)
        raise RuntimeError("Ningún proveedor de STT disponible (ni primario ni fallback).")

    def tts_status(self) -> dict:
        """Qué tier respondería hoy si se pidiera hablar, sin sintetizar nada
        — para /status y el dashboard."""
        tiers = self._config["tts"]["tiers"]
        local = self._tts(tiers["local"])
        premium = self._tts(tiers["premium"])
        if local.available:
            active = "local"
        elif premium.available:
            active = "premium"
        else:
            active = None
        return {"available": active is not None, "active_tier": active}

    def speak(self, text: str, tier: str | None = None) -> bytes:
        """Sintetiza voz. Sin `tier`, usa siempre 'local' (default de toda
        conversación) y NUNCA escala solo a 'hosted'/'premium' — eso requiere
        pedirlo explícito vía `tier=`, después de que quien llama le haya
        avisado al fundador y este haya confirmado."""
        tiers = self._config["tts"]["tiers"]
        target_tier = tier or "local"
        provider_name = tiers.get(target_tier)
        if not provider_name:
            raise RuntimeError(f"tier de voz desconocido: {target_tier}")
        provider = self._tts(provider_name)
        if not provider.available:
            raise TierUnavailable(f"El tier '{target_tier}' de voz no está disponible ahora mismo.")
        return provider.speak(text)
