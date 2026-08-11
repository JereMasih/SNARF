"""Introspección real de Snarf (Fase 5 del plan de observabilidad/n8n — ver
ADR 0140, dejada pendiente explícitamente por ADR 0139: "una API de
introspección real y más completa es trabajo de la Fase 5"). Agrega, en un
solo resultado de solo lectura, señales que ya existen — nunca una segunda
implementación de ninguna: ruteo real de modelos por rol (llm_routing.py),
tools reales del Orchestrator (recibidos como parámetro, ver más abajo), y
el board real de Inteligencia Ejecutiva (snarf/executive/roles.py).

`tools`/`safe_tool_names` se reciben como parámetro en vez de importarse de
`snarf.core.orchestrator` (ADR 0152, Fase 11): este módulo pasó a ser
llamado también desde ADENTRO de un tool real del propio Orchestrator
(`system_introspect`) — importar orchestrator.py acá crearía un ciclo real
(orchestrator.py -> introspection.py -> orchestrator.py). Mismo criterio que
`active_user_sessions` ya recibido como parámetro (ver `system_snapshot`) y
que `ops_health.system_health()`: este módulo nunca sale a buscar sus propias
señales, siempre las recibe de quien sí puede verlas sin ciclos."""

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import llm_routing


def agents_snapshot() -> list[dict]:
    """Ruteo real (proveedor/modelo) de cada rol del sistema, tal cual está
    guardado ahora en data/llm_routing.json — el mismo dato que ya alimenta
    GET /llm_routing para la Configuración del fundador, nunca reinventado."""
    routing = llm_routing.load_routing()
    executive_by_llm_role = {cfg.llm_routing_role: cfg for cfg in ROLE_CONFIGS.values()}
    agents = []
    for role in llm_routing.ROLES:
        entry = routing.get(role, {})
        exec_cfg = executive_by_llm_role.get(role)
        agents.append(
            {
                "role": role,
                "provider": entry.get("provider"),
                "model": entry.get("model"),
                "executive_board_role": exec_cfg.role if exec_cfg else None,
            }
        )
    return agents


def tools_snapshot(tools: list[dict], safe_tool_names: frozenset[str]) -> list[dict]:
    """Nombre + descripción real de cada tool seguro para un segundo
    consumidor — `tools` es `orchestrator.TOOLS` real, `safe_tool_names` es
    el mismo cálculo que ya usa `snarf/mcp/server.py::build_server()`
    (`MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS - BULK_READ_GATED_TOOLS`), ambos
    pasados por el llamador (ver docstring del módulo — evita el ciclo real
    de importar snarf.core.orchestrator acá). Nunca el input_schema
    completo: introspección es "qué puede hacer Snarf", no una superficie de
    invocación remota nueva — n8n observa y propone, nunca ejecuta tools
    directo (ver ADR 0139)."""
    return [
        {"name": tool["name"], "description": tool["description"]}
        for tool in tools
        if tool["name"] in safe_tool_names
    ]


def executive_board_snapshot() -> list[dict]:
    """Los 7 roles reales del board asesor (snarf/executive/roles.py) — rol,
    nombre visible y dominio, ya público en la propia UI de Configuración."""
    return [
        {"role": cfg.role, "display_name": cfg.display_name, "domain": cfg.domain}
        for cfg in ROLE_CONFIGS.values()
    ]


def system_snapshot(
    *, tools: list[dict], safe_tool_names: frozenset[str], active_user_sessions: int | None = None
) -> dict:
    """`active_user_sessions` viene del llamador (app.py conoce el registro
    real de Orchestrator por user_id, ADR 0137) — este módulo no importa
    app.py, mismo criterio que ops_health.system_health() recibiendo sus
    señales como parámetros en vez de ir a buscarlas él mismo. Default
    `None` (nunca inventado): el tool `system_introspect` (ADR 0152) se
    puede invocar desde un consumidor MCP externo de sesión única, que no
    tiene forma real de saber cuántas sesiones web activas hay — `None` es
    la respuesta honesta "no disponible desde acá", no un cero inventado."""
    return {
        "agents": agents_snapshot(),
        "tools": tools_snapshot(tools, safe_tool_names),
        "executive_board": executive_board_snapshot(),
        "active_user_sessions": active_user_sessions,
    }
