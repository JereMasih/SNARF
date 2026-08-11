"""Introspección real de Snarf (Fase 5 del plan de observabilidad/n8n — ver
ADR 0140, dejada pendiente explícitamente por ADR 0139: "una API de
introspección real y más completa es trabajo de la Fase 5"). Agrega, en un
solo resultado de solo lectura, señales que ya existen — nunca una segunda
implementación de ninguna: ruteo real de modelos por rol (llm_routing.py),
tools reales del Orchestrator filtrados por el mismo allowlist ya usado por
MCP (defensa en profundidad idéntica a snarf/mcp/server.py::build_server),
y el board real de Inteligencia Ejecutiva (snarf/executive/roles.py)."""

from snarf.core.orchestrator import BULK_READ_GATED_TOOLS, HIGH_IMPACT_TOOLS, TOOLS
from snarf.executive.roles import ROLE_CONFIGS
from snarf.mcp.tools import MCP_EXPOSED_TOOLS
from snarf.runtime import llm_routing

# Mismo cálculo que build_server() en snarf/mcp/server.py — un solo lugar
# real que decide "qué tool es seguro exponer a un segundo consumidor".
_SAFE_TOOL_NAMES = MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS - BULK_READ_GATED_TOOLS


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


def tools_snapshot() -> list[dict]:
    """Nombre + descripción real de cada tool seguro para un segundo
    consumidor — nunca los de HIGH_IMPACT_TOOLS/BULK_READ_GATED_TOOLS, ni
    los que MCP_EXPOSED_TOOLS ya excluye a propósito (lectura cruda de
    contenido personal). Nunca el input_schema completo: introspección es
    "qué puede hacer Snarf", no una superficie de invocación remota nueva —
    n8n observa y propone, nunca ejecuta tools directo (ver ADR 0139)."""
    return [
        {"name": tool["name"], "description": tool["description"]}
        for tool in TOOLS
        if tool["name"] in _SAFE_TOOL_NAMES
    ]


def executive_board_snapshot() -> list[dict]:
    """Los 7 roles reales del board asesor (snarf/executive/roles.py) — rol,
    nombre visible y dominio, ya público en la propia UI de Configuración."""
    return [
        {"role": cfg.role, "display_name": cfg.display_name, "domain": cfg.domain}
        for cfg in ROLE_CONFIGS.values()
    ]


def system_snapshot(*, active_user_sessions: int) -> dict:
    """`active_user_sessions` viene del llamador (app.py conoce el registro
    real de Orchestrator por user_id, ADR 0137) — este módulo no importa
    app.py, mismo criterio que ops_health.system_health() recibiendo sus
    señales como parámetros en vez de ir a buscarlas él mismo."""
    return {
        "agents": agents_snapshot(),
        "tools": tools_snapshot(),
        "executive_board": executive_board_snapshot(),
        "active_user_sessions": active_user_sessions,
    }
