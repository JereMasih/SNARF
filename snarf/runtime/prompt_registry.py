"""Prompt Registry (Fase 6 del plan de observabilidad/n8n — ver
ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0141). Migra los prompts que
hoy son constantes hardcodeadas en el código a almacenamiento versionado real
— mismo estilo "JSON-por-entidad" que `llm_routing.py`
(`data/llm_routing.json`): un solo archivo (`data/prompts.json`), clave =
`prompt_id`, valor = historial completo de versiones + cuál está activa.

Un `prompt_id` que nunca se tocó no tiene entrada en el archivo — en ese
caso el texto hardcodeado del código sigue siendo lo que corre, tal cual
antes de esta ADR ("nada cambia de comportamiento el día del corte", mismo
criterio que `DEFAULT_ROUTING` en `llm_routing.py`). El primer
`save_new_version()` siembra ese mismo texto como v1 real antes de agregar
la versión nueva — así un rollback a v1 siempre vuelve al comportamiento
original real, nunca a un texto reconstruido a mano.

Esta ADR construye el registro (lectura, guardado, historial, rollback) y
wirea los ~20 prompts reales existentes a leer a través de él. Escribir una
versión nueva desde n8n/el cockpit del fundador es Fase 9.3 — todavía sin
construir; hoy estas funciones solo se llaman desde tests y, a futuro,
desde ese endpoint."""

import json
import time
from pathlib import Path

PROMPTS_PATH = Path("data/prompts.json")

# Los ~20 prompts reales migrados en esta ronda (ver ADR 0141 para la
# correspondencia completa con cada archivo/constante original). Allowlist
# positivo, mismo criterio que MCP_EXPOSED_TOOLS — nunca un id inventado.
PROMPT_IDS: tuple[str, ...] = (
    "orchestrator_system_prefix",
    "conversation_title",
    "history_compaction",
    "drive_vision",
    "gmail_digest",
    "dashboard_curator",
    "project_manager_subfolder_suggestion",
    "project_manager_summary",
    "calendar_brief",
    "morning_routine_classify",
    "morning_routine_synthesize",
    "research_deep_research",
    "research_trend_scan",
    "research_competitor_watch",
    "content_blog_post",
    "content_social_post",
    "content_newsletter",
    "client_status",
    "books_categorize",
    "sponsor_inbox_triage",
    # Fase 13 del roadmap de observabilidad/n8n (extensión de cobertura
    # 2026-08-11, ver ADR correspondiente): los 7 roles del Executive Board
    # (ADR 0094) no tenían prompt_id — su texto vivía inline en
    # snarf/executive/roles.py::_prompt(), no editable vía /n8n/prompts.
    # monthly_pnl y community_pulse quedan afuera a propósito: son
    # determinísticos, sin LLM, sin prompt que editar. El meta-prompt de
    # Skill Factory también queda afuera a propósito (ver ADR): no es un
    # system prompt de LLM plano, es una plantilla con placeholders y
    # guardrails de seguridad reales (alcance de archivos permitidos) —
    # exponerla a edición de texto libre sin validación sería un foot-gun
    # real, distinto en naturaleza a los 27 prompts de este tuple.
    "executive_board_cto",
    "executive_board_coo",
    "executive_board_research",
    "executive_board_ceo",
    "executive_board_cfo",
    "executive_board_cmo",
    "executive_board_creative",
)


def _load_all() -> dict:
    if not PROMPTS_PATH.exists():
        return {}
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


def _save_all(data: dict) -> None:
    PROMPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMPTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_entry(default: str) -> dict:
    return {"active_version": 1, "versions": [{"version": 1, "text": default, "created_at": time.time()}]}


def get_active_text(prompt_id: str, default: str) -> str:
    """El texto real que debe usarse ahora mismo para este prompt: el
    default hardcodeado del código si nunca se guardó una versión nueva, o
    el texto de la versión activa si sí. Llamada en cada uso real (no
    cacheada a nivel de import) — mismo patrón que `load_routing()`, un
    rollback/edición queda vivo de inmediato, sin reiniciar el server."""
    entry = _load_all().get(prompt_id)
    if not entry:
        return default
    versions = {v["version"]: v["text"] for v in entry["versions"]}
    return versions.get(entry["active_version"], default)


def history(prompt_id: str, default: str) -> list[dict]:
    """Historial real de versiones, con `active=True` en la vigente. Si
    nunca se guardó nada, el propio default cuenta como v1 implícito —
    nunca reporta un historial vacío cuando en la práctica sí hay un texto
    real corriendo."""
    entry = _load_all().get(prompt_id)
    if not entry:
        entry = _seed_entry(default)
        entry["versions"][0]["created_at"] = None
    return [{**v, "active": v["version"] == entry["active_version"]} for v in entry["versions"]]


def save_new_version(prompt_id: str, text: str, default: str) -> dict:
    """Guarda `text` como versión nueva y la activa. Si es la primera vez
    que se toca este prompt, siembra la v1 real (el default hardcodeado)
    antes de agregar la v2 — nunca se pierde el texto original."""
    data = _load_all()
    entry = data.get(prompt_id) or _seed_entry(default)
    next_version = max(v["version"] for v in entry["versions"]) + 1
    entry["versions"].append({"version": next_version, "text": text, "created_at": time.time()})
    entry["active_version"] = next_version
    data[prompt_id] = entry
    _save_all(data)
    return entry


def rollback(prompt_id: str, version: int, default: str) -> dict:
    """Activa una versión ya existente del historial — nunca borra ninguna
    (mismo criterio que `fallback_expires_at` en `llm_routing.py`: nada se
    pierde solo por dejar de ser la versión activa)."""
    data = _load_all()
    entry = data.get(prompt_id) or _seed_entry(default)
    valid_versions = {v["version"] for v in entry["versions"]}
    if version not in valid_versions:
        raise ValueError(f"Versión {version} no existe para el prompt {prompt_id!r}")
    entry["active_version"] = version
    data[prompt_id] = entry
    _save_all(data)
    return entry
