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

# Groq, speech-to-text (whisper-large-v3-turbo). Fuente: groq.com/pricing,
# verificado 2026-07-30. Factura con un piso efectivo de ~10s por request
# (ver GROQ_STT_MIN_BILLED_SECONDS) — clips más cortos igual pagan el piso.
GROQ_STT_USD_PER_HOUR = 0.04
GROQ_STT_MIN_BILLED_SECONDS = 10

# Voyage AI, embeddings. Fuente: docs.voyageai.com/docs/pricing, verificado 2026-07-28.
VOYAGE_RATES_PER_MILLION_TOKENS = {
    "voyage-4-lite": 0.02,
    "voyage-4": 0.06,
    "voyage-4-large": 0.12,
}
VOYAGE_FREE_TOKENS_PER_ACCOUNT = 200_000_000


# Precios reales de proveedores alternativos de LLM, investigados con
# búsqueda web el 2026-07-30 (ver ADR de "LLM multi-proveedor") — nunca
# estimados de memoria (Principio VI de FOUNDATION.md). Un modelo pedido que
# no está en la tabla usa el DEFAULT_* de ese proveedor (el más económico
# conocido, para no sobreestimar el gasto real por un modelo nuevo sin
# tarifa registrada todavía).
GEMINI_RATES_PER_MILLION_TOKENS = {
    "gemini-3-pro-preview": (2.0, 12.0),
    "gemini-3.1-pro-preview": (2.0, 12.0),
    # gemini-2.5-flash y gemini-2.5-flash-lite: verificado con una llamada
    # real el 2026-07-30 que la API ya los rechaza para keys nuevas (404 "no
    # longer available to new users") — se dejan las tarifas por si alguna
    # key vieja los sigue teniendo habilitados, pero el default ya no apunta
    # ahí.
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.1-flash-lite": (0.25, 1.50),
}
DEFAULT_GEMINI_RATE = GEMINI_RATES_PER_MILLION_TOKENS["gemini-3.1-flash-lite"]

OPENAI_RATES_PER_MILLION_TOKENS = {
    "gpt-5": (0.625, 5.0),
    "gpt-5.4": (2.50, 15.0),
    "gpt-5.5": (5.0, 30.0),
    "gpt-5.6-sol": (5.0, 30.0),
    "gpt-5.6-terra": (2.50, 15.0),
    "gpt-5.6-luna": (1.0, 6.0),
}
DEFAULT_OPENAI_RATE = OPENAI_RATES_PER_MILLION_TOKENS["gpt-5"]

#  Nomenclatura real de xAI: guiones, no puntos — verificado con una llamada
# real el 2026-07-30 ("grok-4.1-fast" da 400 Model not found; "grok-4-1-fast"
# funciona). Se corrige acá para las tres variantes por consistencia, aunque
# solo la de abajo se confirmó con una llamada real.
XAI_RATES_PER_MILLION_TOKENS = {
    "grok-4-5": (2.0, 6.0),
    "grok-4-3": (1.25, 2.50),
    "grok-4-1-fast": (0.20, 0.50),
}
DEFAULT_XAI_RATE = XAI_RATES_PER_MILLION_TOKENS["grok-4-1-fast"]

GROQ_LLAMA_RATES_PER_MILLION_TOKENS = {
    "llama-4-maverick": (0.20, 0.60),
    "llama-4-scout": (0.08, 0.30),
    # Precio real verificado por búsqueda web el 2026-08-06 (varias fuentes
    # coinciden: $0.59/$0.79 el millón) — reemplaza a "llama-4-scout" como
    # RECOMMENDED_MODEL de groq_llama (ese modelo ya no existe en la API
    # real de Groq, confirmado con una llamada real este mismo día).
    "llama-3.3-70b-versatile": (0.59, 0.79),
}
DEFAULT_GROQ_LLAMA_RATE = GROQ_LLAMA_RATES_PER_MILLION_TOKENS["llama-3.3-70b-versatile"]


def estimate_generic_llm_cost(
    rates: dict, default_rate: tuple, model: str, input_tokens: int, output_tokens: int
) -> float:
    """Estimador simple (input+output, sin descuento de cache) para
    proveedores sin la mecánica de cache_control propia de Anthropic."""
    input_rate, output_rate = rates.get(model, default_rate)
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


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


def estimate_groq_stt_cost(duration_seconds: float) -> float:
    billed_seconds = max(duration_seconds, GROQ_STT_MIN_BILLED_SECONDS)
    return (billed_seconds / 3600) * GROQ_STT_USD_PER_HOUR


def estimate_voyage_cost(model: str, tokens: int, cumulative_tokens_before: int) -> float:
    rate = VOYAGE_RATES_PER_MILLION_TOKENS.get(model, VOYAGE_RATES_PER_MILLION_TOKENS["voyage-4-lite"])
    free_remaining = max(VOYAGE_FREE_TOKENS_PER_ACCOUNT - cumulative_tokens_before, 0)
    billable_tokens = max(tokens - free_remaining, 0)
    return (billable_tokens / 1_000_000) * rate
