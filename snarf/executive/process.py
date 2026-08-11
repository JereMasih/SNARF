"""Consulta real a un rol de Inteligencia Ejecutiva (ver ADR 0094/0098): un
subproceso corto por consulta, nunca un daemon persistente ni una llamada
in-process a Orchestrator._handle_tool(). Esto es deliberado, no solo un
detalle de implementación — es la razón real por la que se reabrió MCP
(ADR 0093): el rol corre como un segundo consumidor genuino de las
herramientas de Snarf, con su propia sesión de cliente MCP, aislado del
Orchestrator principal.

AnthropicLLM.generate() es síncrono y llama a tool_handler() síncronamente
desde adentro de su propio loop de rondas — pero una sesión de cliente MCP
real es asincrónica de punta a punta (stdio_client/ClientSession). El puente
de abajo corre esa sesión en un hilo propio con su loop de asyncio activo
(run_forever) y expone un call_tool() síncrono que bloquea hasta el
resultado real vía run_coroutine_threadsafe — sin eso, no hay forma de
llamar a una tool real de MCP desde adentro de un tool_handler síncrono."""

import asyncio
import json
import sys
import threading
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from snarf.executive.opinion import parse_opinions
from snarf.executive.roles import ExecutiveRoleConfig
from snarf.telemetry import context

REPO_ROOT = Path(__file__).resolve().parents[2]
_BRIDGE_TIMEOUT_SECONDS = 30
_TOOL_CALL_TIMEOUT_SECONDS = 60


class _MCPToolBridge:
    def __init__(self, repo_root: Path = REPO_ROOT):
        # env=context.env_for_child_process() (Fase 1 del plan de
        # observabilidad): único modo real de cruzar el límite de proceso —
        # el subproceso MCP no hereda contextvars, solo lo que se le pase
        # acá. `StdioServerParameters.env` se MERGEA (nunca reemplaza) con
        # el allowlist de entorno por defecto del SDK de MCP
        # (HOME/LOGNAME/PATH/SHELL/TERM/USER), así que esto es seguro: no
        # pisa nada, solo agrega SNARF_TRACE_ID/SNARF_PARENT_EVENT_ID
        # cuando hay una traza real activa (diccionario vacío si no).
        self._server_params = StdioServerParameters(
            command=sys.executable, args=[str(repo_root / "mcp_server.py")], cwd=str(repo_root),
            env=context.env_for_child_process(),
        )
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._stdio_cm = None
        self._session_cm = None
        self._session: ClientSession | None = None

    def start(self, tool_subset: frozenset[str]) -> list[dict]:
        self._thread.start()
        return asyncio.run_coroutine_threadsafe(self._async_start(tool_subset), self._loop).result(
            timeout=_BRIDGE_TIMEOUT_SECONDS
        )

    async def _async_start(self, tool_subset: frozenset[str]) -> list[dict]:
        self._stdio_cm = stdio_client(self._server_params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        listed = await self._session.list_tools()
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in listed.tools
            if t.name in tool_subset
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        return asyncio.run_coroutine_threadsafe(self._async_call_tool(name, arguments), self._loop).result(
            timeout=_TOOL_CALL_TIMEOUT_SECONDS
        )

    async def _async_call_tool(self, name: str, arguments: dict) -> dict:
        result = await self._session.call_tool(name, arguments)
        text = "".join(getattr(block, "text", "") for block in result.content)
        if result.is_error:
            return {"error": text or f"el tool '{name}' falló del lado del servidor MCP"}
        if result.structured_content is not None:
            return result.structured_content
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"result": text}

    def close(self) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self._async_close(), self._loop).result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    async def _async_close(self) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(None, None, None)
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(None, None, None)


def consult_role(role_config: ExecutiveRoleConfig, question: str, llm, repo_root: Path = REPO_ROOT) -> dict:
    """Consulta real a un rol: levanta su propio proceso MCP, corre el loop
    de herramientas de `llm` contra su subset real, y devuelve
    {headline, opinions, raw}. Nunca inventa una opinión si el LLM del rol no
    está disponible — degrada honesto, mismo criterio que
    DashboardCuratorSpecialist/GmailDigestSpecialist."""
    if not llm.available:
        return {
            "headline": f"No se pudo consultar: falta configurar el modelo de lenguaje del rol {role_config.role}.",
            "opinions": [],
            "raw": "",
        }

    bridge = _MCPToolBridge(repo_root)
    try:
        tools = bridge.start(role_config.mcp_tool_subset)
        called_tools: set[str] = set()

        def tool_handler(name: str, tool_input: dict) -> dict:
            called_tools.add(name)
            return bridge.call_tool(name, tool_input)

        response = llm.generate(
            system=role_config.system_prompt,
            messages=[{"role": "user", "content": question}],
            tools=tools,
            tool_handler=tool_handler,
        )
        headline, opinions = parse_opinions(response.text, called_tools)
        return {
            "headline": headline,
            "opinions": [{"claim": o.claim, "basis": o.basis, "source": o.source} for o in opinions],
            "raw": response.text,
        }
    except Exception as exc:
        return {"headline": f"No se pudo consultar a {role_config.role}: {exc}", "opinions": [], "raw": ""}
    finally:
        bridge.close()
