"""Cuarto punto de entrada de Snarf, hermano de main.py/main.py --voice/app.py
— todos sobre el mismo Orchestrator (ver ADR 0006/0007). Este arranca el
servidor MCP real (ver ADR 0093) para el primer segundo consumidor de las
herramientas de Snarf: los procesos de Inteligencia Ejecutiva (COGNITION.md,
ADR 0094). Transporte stdio — pensado para ser lanzado como proceso hijo por
sesión, nunca como servidor de red persistente."""

from dotenv import load_dotenv

load_dotenv()

from snarf.core.orchestrator import DEFAULT_USER_ID, Orchestrator
from snarf.mcp.server import build_server
from snarf.telemetry import context


def main():
    # context.adopt_from_env (Fase 1 del plan de observabilidad): si este
    # subproceso fue lanzado por _MCPToolBridge (ver
    # snarf/executive/process.py) con una traza real activa del lado del
    # padre, la adopta acá — así los tool.started/tool.finished que dispare
    # este Orchestrator (mismo _handle_tool de siempre, ver
    # snarf/mcp/server.py) quedan correlacionados con el turno/consulta que
    # los originó, en vez de aparecer sin relación en telemetry_events.jsonl.
    # No-op honesto (ninguna traza adoptada) cuando se lanza sin ese
    # contexto — nunca inventa una.
    context.adopt_from_env()
    orchestrator = Orchestrator(user_id=DEFAULT_USER_ID)
    server = build_server(orchestrator)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
