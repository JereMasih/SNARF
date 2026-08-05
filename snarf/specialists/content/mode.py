from dataclasses import dataclass

_HONESTY_SUFFIX = (
    "Si te dan material de referencia real, basate en él para cualquier dato/afirmación concreta "
    "sobre el fundador, su negocio o su producto — nunca inventes una cifra, cliente, resultado o "
    "hecho concreto que no esté en ese material. El resto (tono, estructura, ganchos narrativos) es "
    "tu trabajo creativo, sin restricción."
)


@dataclass(frozen=True)
class ContentModeConfig:
    mode: str
    display_name: str
    system_prompt: str
    llm_routing_role: str


BLOG_POST_CONFIG = ContentModeConfig(
    mode="blog_post",
    display_name="Post de Blog",
    system_prompt=(
        "Escribís posts de blog para el fundador de Snarf, en español, con estructura clara "
        f"(título, introducción, desarrollo en secciones, cierre). {_HONESTY_SUFFIX}"
    ),
    llm_routing_role="content_blog_post",
)

SOCIAL_POST_CONFIG = ContentModeConfig(
    mode="social_post",
    display_name="Post de Redes",
    system_prompt=(
        "Escribís posts cortos para redes sociales (estilo directo, sin relleno, pensado para "
        f"generar reacción real, no genérico). {_HONESTY_SUFFIX}"
    ),
    llm_routing_role="content_social_post",
)

NEWSLETTER_CONFIG = ContentModeConfig(
    mode="newsletter",
    display_name="Newsletter",
    system_prompt=(
        "Escribís newsletters para el fundador de Snarf: tono personal y directo, como si le "
        f"escribiera él mismo a su lista, no un comunicado corporativo genérico. {_HONESTY_SUFFIX}"
    ),
    llm_routing_role="content_newsletter",
)

CONTENT_MODE_CONFIGS: dict[str, ContentModeConfig] = {
    c.mode: c for c in (BLOG_POST_CONFIG, SOCIAL_POST_CONFIG, NEWSLETTER_CONFIG)
}
