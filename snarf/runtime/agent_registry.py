"""Agent/Capability Registry (Fase 16 del plan de observabilidad/n8n — ver
ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0157). Único punto de
lectura de la "receta" completa de un rol del Executive Board: prompt +
tool_subset + routing + stages — compone los cuatro registros ya
versionados (prompt_registry, tool_subset_registry, llm_routing,
agent_graph_registry) sin storage propio. Cualquier código que necesite
saber "qué tiene configurado este agente ahora mismo" (Fase 17: motor de
stages; Fase 18: generador n8n; Fase 19: endpoints propose/apply) debe
llamar a get_agent_recipe() acá, nunca leer los cuatro registros sueltos por
su cuenta — mismo principio de chokepoint único que ya rige
Orchestrator._handle_tool().

Alcance honesto (Fase 16): solo los 7 roles del Executive Board tienen una
receta completa acá. tool_subset y stages son conceptos específicos del
patrón MCP-multi-proceso de snarf/executive/ — los demás Specialists
(snarf/specialists/*) no tienen ningún concepto de "MCP tool subset" propio
ni participan de ninguna secuencia entre agentes, así que forzarles esos dos
ejes sería inventar una capacidad que el código no sostiene (Principio VI,
FOUNDATION.md). Esos Specialists sí tienen prompt versionado
(prompt_registry.PROMPT_IDS) y, la mayoría, un rol de ruteo propio
(llm_routing.ROLES) — pero ningún consumidor real necesita hoy una "receta"
compuesta para ellos vía este módulo; leerlos directo de prompt_registry/
llm_routing alcanza. Generalizar get_agent_recipe() más allá del board queda
para cuando un consumidor real (Fase 18+) lo necesite, no antes."""

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_graph_registry, llm_routing, prompt_registry, tool_subset_registry


def _resolve_role(agent_id: str) -> str:
    """"cto" y "executive_board_cto" resuelven al mismo rol corto — el
    primero es el `role` real de ExecutiveRoleConfig, el segundo es el
    prompt_id/namespace que ya usan prompt_registry y los workflows de n8n
    (ver ADR 0153). Acepta ambas formas para que un caller no tenga que
    saber cuál convención usa cada registro."""
    if agent_id in ROLE_CONFIGS:
        return agent_id
    if agent_id.startswith("executive_board_"):
        short = agent_id.removeprefix("executive_board_")
        if short in ROLE_CONFIGS:
            return short
    raise ValueError(
        f"agent_id desconocido para el Agent Registry: {agent_id!r}. "
        f"Roles válidos del Executive Board: {', '.join(ROLE_CONFIGS)} "
        f"(también aceptan el prefijo 'executive_board_')."
    )


def get_agent_recipe(agent_id: str) -> dict:
    """Receta completa y actual de un rol del Executive Board — prompt,
    tools, routing y stages, cada uno con su valor activo real y su
    historial. Lanza ValueError para cualquier agent_id que no sea uno de
    los 7 roles del board (ver docstring del módulo)."""
    role = _resolve_role(agent_id)
    config = ROLE_CONFIGS[role]
    prompt_id = f"executive_board_{role}"
    routing_role = config.llm_routing_role

    return {
        "agent_id": role,
        "display_name": config.display_name,
        "domain": config.domain,
        "prompt": {
            "prompt_id": prompt_id,
            "active_text": prompt_registry.get_active_text(prompt_id, config.system_prompt),
            "history": prompt_registry.history(prompt_id, config.system_prompt),
        },
        "tools": {
            "active": sorted(tool_subset_registry.get_active_subset(role, config.mcp_tool_subset)),
            "history": tool_subset_registry.history(role, config.mcp_tool_subset),
        },
        "routing": {
            "routing_role": routing_role,
            "active": llm_routing.load_routing().get(routing_role, llm_routing.DEFAULT_ROUTING[routing_role]),
            "history": llm_routing.routing_history(routing_role),
        },
        "stages": {
            "active": agent_graph_registry.get_active_stages(),
            "history": agent_graph_registry.history(),
        },
    }
