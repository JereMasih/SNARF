import os

from snarf.capabilities.base import Capability
from snarf.telemetry import usage_tracker

# El más barato de la familia vigente (voyage-4), con 200M tokens gratis por
# cuenta — ver snarf/telemetry/pricing.py y el ADR que introdujo esta pieza.
DEFAULT_MODEL = "voyage-4-lite"


class VoyageEmbeddings(Capability):
    name = "voyage_embeddings"

    def __init__(self, model: str = DEFAULT_MODEL, max_retries: int = 5):
        self.model = model
        self._api_key = os.environ.get("VOYAGE_API_KEY")
        self._client = None
        if self._api_key:
            import voyageai

            # Cuentas sin método de pago cargado en Voyage quedan limitadas a
            # 3 RPM — sin reintentos, la mayoría de los embeds de una corrida
            # real fallan por rate limit, no por falta de crédito. El SDK ya
            # sabe respetar el header retry-after; se lo delegamos en vez de
            # reinventar el backoff acá.
            self._client = voyageai.Client(api_key=self._api_key, max_retries=max_retries)

    @property
    def available(self) -> bool:
        return self._client is not None

    def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        if not self._client:
            raise RuntimeError("VOYAGE_API_KEY no configurada (ver .env.example).")
        result = self._client.embed(texts, model=self.model, input_type=input_type)
        usage_tracker.record_voyage_call(self.model, result.total_tokens)
        return result.embeddings
