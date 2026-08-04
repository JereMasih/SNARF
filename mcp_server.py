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


def main():
    orchestrator = Orchestrator(user_id=DEFAULT_USER_ID)
    server = build_server(orchestrator)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
