"""Servidor MCP real de Snarf (ver ADR 0093) — expone el allowlist de
snarf/mcp/tools.py a un segundo consumidor real de las herramientas de
Snarf (los procesos de Inteligencia Ejecutiva, ver COGNITION.md/ADR 0094).

Nunca reimplementa la lógica de un tool: cada wrapper generado acá delega,
sin excepción, a `Orchestrator._handle_tool()` — mismo camino de despacho,
misma instrumentación de activity_log/events que el Orchestrator principal.
El SDK real instalado (paquete `mcp`, verificado campo por campo antes de
escribir este archivo, no asumido) construye el JSON Schema de cada tool
introspeccionando la firma de una función Python — por eso cada wrapper se
genera dinámicamente a partir del `input_schema` real que ya vive en
`orchestrator.TOOLS`, en vez de mantener el schema escrito dos veces."""

import inspect
from typing import Any

from mcp.server.mcpserver import MCPServer

from snarf.core.orchestrator import BULK_READ_GATED_TOOLS, HIGH_IMPACT_TOOLS, TOOLS, Orchestrator
from snarf.mcp.tools import MCP_EXPOSED_TOOLS

_JSON_TYPE_TO_PY: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _make_wrapper(tool_name: str, schema: dict, orchestrator: Orchestrator):
    """Función Python real, con firma tipada generada desde el JSON Schema
    real del tool — el SDK de MCP la introspecciona para construir el
    inputSchema que expone al cliente. El cuerpo nunca hace más que empaquetar
    los kwargs y delegar a Orchestrator._handle_tool(), la misma ruta que usa
    el Orchestrator principal."""
    properties: dict = schema.get("properties", {})
    required = set(schema.get("required", []))
    parameters = []
    for name, prop_schema in properties.items():
        py_type = _JSON_TYPE_TO_PY.get(prop_schema.get("type"), str)
        if name in required:
            default = inspect.Parameter.empty
        else:
            default = None
            py_type = py_type | None
        parameters.append(
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default, annotation=py_type)
        )

    def wrapper(**kwargs: Any):
        # None es el default real de un parámetro opcional no provisto (ver
        # arriba) — nunca se lo pasamos al Orchestrator como si el cliente lo
        # hubiese pedido explícitamente, mismo criterio que ya usan los
        # handlers de orchestrator.py con dict.get().
        tool_input = {k: v for k, v in kwargs.items() if v is not None}
        return orchestrator._handle_tool(tool_name, tool_input)

    wrapper.__name__ = tool_name
    wrapper.__signature__ = inspect.Signature(parameters)
    return wrapper


def build_server(orchestrator: Orchestrator | None = None) -> MCPServer:
    """Arma el servidor MCP real, filtrando orchestrator.TOOLS por el
    allowlist. Nunca expone un tool de HIGH_IMPACT_TOOLS/BULK_READ_GATED_TOOLS
    aunque alguien lo agregara por error al allowlist (defensa en profundidad,
    ver tests/test_mcp_server.py) — la Inteligencia Ejecutiva (ADR 0094) no
    ejecuta herramientas, solo lee agregados reales."""
    orchestrator = orchestrator or Orchestrator()
    server = MCPServer("snarf-knowledge", version="1.0")

    exposed = MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS - BULK_READ_GATED_TOOLS
    tools_by_name = {t["name"]: t for t in TOOLS}
    for name in sorted(exposed):
        tool = tools_by_name.get(name)
        if tool is None:
            # Un nombre del allowlist que ya no existe en el Orchestrator
            # (renombrado o eliminado) nunca debe romper el arranque del
            # servidor en silencio ni exponer nada — se salta, y el test de
            # cobertura (allowlist ⊆ tools reales) es quien debe fallar.
            continue
        wrapper = _make_wrapper(name, tool.get("input_schema", {}), orchestrator)
        server.add_tool(wrapper, name=name, description=tool.get("description", ""))

    return server
