from snarf.core.orchestrator import TOOLS
from snarf.telemetry import brain, verbs


def test_verbo_tematico_uses_the_node_specific_entry():
    assert verbs.verbo_tematico("drive", "capability") == "hojeando"
    assert verbs.verbo_tematico("llm", "capability") == "pontificando"


def test_verbo_tematico_falls_back_to_agente_for_an_unmapped_node():
    assert verbs.verbo_tematico("nodo_nuevo_sin_entrada", "capability") == "operando"
    assert verbs.verbo_tematico("nodo_nuevo_sin_entrada", "specialist") == "delegando"


def test_verbo_tematico_prefixes_the_error_modifier_without_dropping_the_base_verb():
    assert verbs.verbo_tematico("drive", "capability", estado="error") == "tropezando con hojeando"


def test_verbo_tematico_prefixes_the_truncado_modifier():
    assert verbs.verbo_tematico("llm", "capability", estado="truncado") == "conteniéndose en pontificando"


def test_every_real_node_has_an_entry_or_a_safe_agente_fallback():
    # No es obligatorio que cada nodo tenga entrada propia (el fallback por
    # agente existe justo para eso), pero si un nodo nuevo aparece en
    # brain.py sin entrada propia y sin agente conocido, verbo_tematico no
    # debe romper — este test lo deja como red de seguridad.
    for node_id, tier in brain.NODE_TIER.items():
        verb = verbs.verbo_tematico(node_id, tier)
        assert isinstance(verb, str) and verb


def test_verb_by_skill_covers_every_orchestrator_tool():
    # Regresión: si se agrega una tool nueva a Orchestrator y se olvida
    # sumarle un verbo propio acá, este test lo detecta — mismo criterio
    # que test_tool_to_node_covers_every_orchestrator_tool en test_brain.py.
    real_tool_names = {tool["name"] for tool in TOOLS}
    assert set(verbs.VERB_BY_SKILL.keys()) == real_tool_names


def test_verbo_tematico_prefers_the_skill_specific_verb_over_the_node_verb():
    # drive_delete_file y drive_list_files caen en el mismo nodo "drive" —
    # antes compartían el mismo verbo genérico, ahora cada uno tiene el suyo.
    assert verbs.verbo_tematico("drive", "capability", skill="drive_delete_file") == "borrando el archivo"
    assert verbs.verbo_tematico("drive", "capability", skill="drive_list_files") == "hojeando el Drive"


def test_verbo_tematico_falls_back_to_node_verb_when_skill_is_a_vendor_call():
    # Las llamadas de vendor (ej. "anthropic:claude-sonnet-5") no son tools
    # con nombre propio — no están en VERB_BY_SKILL, caen al nodo.
    assert verbs.verbo_tematico("llm", "capability", skill="anthropic:claude-sonnet-5") == "pontificando"


def test_verbo_tematico_applies_the_estado_modifier_to_a_skill_specific_verb():
    assert (
        verbs.verbo_tematico("gmail_send", "capability", estado="error", skill="gmail_send_message")
        == "tropezando con despachando el correo"
    )
