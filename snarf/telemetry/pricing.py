# Tarifas públicas usadas para ESTIMAR costo — no son el saldo real de ninguna
# cuenta (eso solo lo tienen los paneles de Anthropic/ElevenLabs/Voyage). Se
# revisan a mano cuando cambian los precios publicados; fuente y fecha de
# verificación en el ADR que introdujo cada una.

# (input, output) en USD por millón de tokens. Fuente: claude.com/pricing y
# docs.anthropic.com, verificado 2026-07-28.
ANTHROPIC_RATES_PER_MILLION_TOKENS = {
    "claude-sonnet-5": (2.0, 10.0),  # vigente hasta 2026-08-31; después $3/$15
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5": (5.0, 25.0),
}
DEFAULT_ANTHROPIC_RATE = ANTHROPIC_RATES_PER_MILLION_TOKENS["claude-sonnet-5"]
# Un hit de cache cuesta 10% del input estándar (prompt caching de Anthropic).
ANTHROPIC_CACHE_READ_DISCOUNT = 0.1

# ElevenLabs Scribe (speech-to-text), pago por uso. Fuente: elevenlabs.io/pricing/api,
# verificado 2026-07-28.
ELEVENLABS_STT_USD_PER_HOUR = 0.22

# Voyage AI, embeddings. Fuente: docs.voyageai.com/docs/pricing, verificado 2026-07-28.
VOYAGE_RATES_PER_MILLION_TOKENS = {
    "voyage-4-lite": 0.02,
    "voyage-4": 0.06,
    "voyage-4-large": 0.12,
}
VOYAGE_FREE_TOKENS_PER_ACCOUNT = 200_000_000


def estimate_anthropic_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    input_rate, output_rate = ANTHROPIC_RATES_PER_MILLION_TOKENS.get(model, DEFAULT_ANTHROPIC_RATE)
    # input_tokens que devuelve la API ya excluye lo servido desde cache; se
    # suma aparte con su propia tarifa (creación de cache = tarifa normal,
    # lectura de cache = 10% de la tarifa normal).
    standard_input_cost = (input_tokens / 1_000_000) * input_rate
    cache_creation_cost = (cache_creation_tokens / 1_000_000) * input_rate
    cache_read_cost = (cache_read_tokens / 1_000_000) * input_rate * ANTHROPIC_CACHE_READ_DISCOUNT
    output_cost = (output_tokens / 1_000_000) * output_rate
    return standard_input_cost + cache_creation_cost + cache_read_cost + output_cost


def estimate_stt_cost(duration_seconds: float) -> float:
    hours = duration_seconds / 3600
    return hours * ELEVENLABS_STT_USD_PER_HOUR


def estimate_voyage_cost(model: str, tokens: int, cumulative_tokens_before: int) -> float:
    rate = VOYAGE_RATES_PER_MILLION_TOKENS.get(model, VOYAGE_RATES_PER_MILLION_TOKENS["voyage-4-lite"])
    free_remaining = max(VOYAGE_FREE_TOKENS_PER_ACCOUNT - cumulative_tokens_before, 0)
    billable_tokens = max(tokens - free_remaining, 0)
    return (billable_tokens / 1_000_000) * rate
