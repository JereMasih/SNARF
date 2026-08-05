from dataclasses import dataclass

_HONESTY_SUFFIX = (
    "Basate ÚNICAMENTE en las fuentes reales que se te dan a continuación — nunca inventes un dato, "
    "cifra, fuente o afirmación que no esté ahí. Si las fuentes disponibles son limitadas o "
    "insuficientes para una conclusión sólida, decilo explícito en vez de completar el vacío. "
    "Citá de qué fuente real sale cada afirmación importante."
)


@dataclass(frozen=True)
class ResearchModeConfig:
    mode: str
    display_name: str
    system_prompt: str
    llm_routing_role: str


DEEP_RESEARCH_CONFIG = ResearchModeConfig(
    mode="deep_research",
    display_name="Investigación Profunda",
    system_prompt=(
        "Investigás un tema a fondo para el fundador de Snarf. Sintetizá las fuentes reales en un "
        "informe estructurado en Markdown: contexto, hallazgos principales, y una conclusión clara. "
        f"{_HONESTY_SUFFIX}"
    ),
    llm_routing_role="research_deep_research",
)

TREND_SCAN_CONFIG = ResearchModeConfig(
    mode="trend_scan",
    display_name="Rastreo de Tendencias",
    system_prompt=(
        "Rastreás tendencias emergentes sobre un tema para el fundador de Snarf. A partir de las "
        "fuentes reales, identificá patrones que se repiten entre varias fuentes distintas (nunca "
        "una tendencia basada en una sola mención) y señalá qué tan reciente/consistente es cada "
        f"una. {_HONESTY_SUFFIX}"
    ),
    llm_routing_role="research_trend_scan",
)

COMPETITOR_WATCH_CONFIG = ResearchModeConfig(
    mode="competitor_watch",
    display_name="Vigilancia de Competencia",
    system_prompt=(
        "Analizás actores/competidores reales de un mercado o nicho para el fundador de Snarf, a "
        "partir de las fuentes reales — qué están haciendo, qué posicionamiento tienen, qué se "
        f"puede aprender de ellos. {_HONESTY_SUFFIX}"
    ),
    llm_routing_role="research_competitor_watch",
)

RESEARCH_MODE_CONFIGS: dict[str, ResearchModeConfig] = {
    c.mode: c for c in (DEEP_RESEARCH_CONFIG, TREND_SCAN_CONFIG, COMPETITOR_WATCH_CONFIG)
}
