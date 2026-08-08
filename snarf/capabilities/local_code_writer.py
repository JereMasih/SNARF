"""Motor de escritura de código de la Skill Factory (ver ADR 0095/0102/0130)
— reemplaza a `snarf/capabilities/claude_code.py` (eliminado en esta ronda),
que invocaba el CLI real de Claude Code como subproceso. Pedido explícito
del fundador tras quedarse sin crédito de la API de Anthropic en un intento
real: quiere que la Skill Factory pueda construir usando el modelo local de
su Mac. Investigado en vivo antes de escribir código (`claude --help`,
versión 2.1.220 real instalada): el CLI de Claude Code NO tiene ninguna
forma soportada de apuntar a un modelo no-Claude — `--model` solo acepta
alias/nombres reales de Claude, los únicos "otros backends" son
Bedrock/Vertex/Foundry, que siguen sirviendo modelos Claude (solo cambia la
nube de facturación). No hay forma de "hacer que el CLI use el modelo
local" — por eso esto es un motor nuevo separado, con la misma interfaz que
`ClaudeCode` tenía (mismo shape de resultado), no una configuración distinta
del mismo CLI.

A diferencia de una sesión real de Claude Code (agente de propósito general,
acceso amplio), acá el modelo local corre un loop de herramientas
deliberadamente angosto: nunca Bash sin restricción, nunca escritura fuera
de un alcance calculado por SkillFactorySpecialist ANTES de invocar esto
(mismo alcance que antes solo se verificaba después vía diff de git — ahora
también gateado en el momento, defensa en profundidad). Edita los archivos
de wiring ya existentes con reemplazo exacto de string — misma semántica
segura que la propia tool Edit: falla si `old_string` no aparece exactamente
una vez, nunca reescribe un archivo entero a ciegas.

Motivo real, verificado en esta misma jornada (no hipotético): un modelo
local de 4B, en la conversación real del fundador, inventó un id de Gmail
inexistente y una tool que no existía. Un modelo local escribiendo código
real tiene el mismo riesgo — por eso la doble verificación de
SkillFactorySpecialist (diff de git + suite completa de tests) sigue intacta
sin cambios: este motor puede fallar seguido, y esa es la razón exacta por
la que la construcción nunca se da por exitosa solo por lo que el modelo
diga de sí mismo."""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from snarf.capabilities.base import Capability

# Rondas de tool-calling reales que puede necesitar una construcción de
# skill completa: leer un ejemplo real, escribir 2-3 archivos nuevos, editar
# 4 archivos de wiring uno por uno, correr la suite, y (si falla) al menos
# un ciclo de leer-el-error + corregir + re-test. MAX_TOOL_ROUNDS=5 (default
# de openai_compatible_llm.py) es el número correcto para el chat
# interactivo, donde la latencia real importa — acá no: build_skill() ya
# corre en background tras una confirmación explícita del fundador, nunca
# bloqueando una conversación en vivo.
MAX_BUILD_TOOL_ROUNDS = 40

SYSTEM_PROMPT = (
    "Sos el motor de escritura de código de la Skill Factory de Snarf (ver ADR 0095/0102/0130). Tu "
    "única tarea: construir UN Specialist nuevo siguiendo EXACTAMENTE la convención real del repo, "
    "usando solo las herramientas que tenés — nunca inventes una que no esté en la lista; si un path "
    "te lo rechaza por estar fuera de alcance, es un límite real, no un error tuyo: corregí el path y "
    "seguí. Trabajá en este orden: (1) leé con read_file el ejemplo real que te paso para copiar el "
    "patrón exacto (imports, forma de la clase, INPUT_SCHEMA/OUTPUT_SCHEMA); (2) escribí con "
    "write_file el módulo del Specialist nuevo y su test — solo esos dos son archivos NUEVOS; (3) "
    "sumá su wiring (tool en TOOLS/_tool_handlers del Orchestrator, nodo en brain.py, verbo en "
    "verbs.py, extractor en detail.py) con edit_file, una edición quirúrgica a la vez sobre archivos "
    "que YA EXISTEN — nunca los reescribas enteros; (4) corré run_tests. Si falla, leé el error real "
    "en la salida y corregí SIEMPRE en el archivo donde está el error real, nunca en otro lado: si el "
    "bug está en el Specialist o el test que vos mismo escribiste, volvé a llamar write_file sobre ese "
    "mismo path para reescribirlo completo con la corrección — dentro de tu propio alcance de "
    "escritura no hay diferencia entre 'crear' y 'corregir', siempre es tu propio archivo nuevo, y "
    "podés llamarla las veces que haga falta. edit_file es solo para los 4 archivos de wiring que YA "
    "EXISTÍAN antes de que empezaras (nunca la uses ni la necesitás para tu propio Specialist/test). "
    "Repetí el ciclo corregir-y-testear hasta que pase la suite ENTERA, no solo los tests nuevos. "
    "Terminá tu respuesta con la palabra LISTO cuando la suite completa haya pasado de verdad, o con "
    "NO PUDE: <motivo real> si te quedaste sin forma de resolverlo — nunca digas LISTO sin haber "
    "corrido run_tests y visto pasar la suite."
)


@dataclass(frozen=True)
class LocalCodeWriterResult:
    ok: bool
    result_text: str
    session_id: str | None
    cost_usd: float | None
    num_turns: int | None
    raw: dict


def _default_run_tests(repo_root: Path) -> dict:
    result = subprocess.run(
        [str(repo_root / ".venv" / "bin" / "python"), "-m", "pytest", "-q"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"passed": result.returncode == 0, "output": (result.stdout + result.stderr)[-3000:]}


class LocalCodeWriter(Capability):
    name = "local_code_writer"

    def __init__(self, llm_factory: Callable, repo_root: Path, run_tests_fn: Callable | None = None):
        # llm_factory (nunca una instancia fija): mismo criterio que el
        # resto de los Specialists de este repo — un cambio de
        # proveedor/modelo del rol "skill_factory_writer" desde
        # Configuración se refleja sin reiniciar el server.
        self._llm_factory = llm_factory
        self._repo_root = repo_root
        self._run_tests_fn = run_tests_fn or (lambda: _default_run_tests(repo_root))

    @property
    def available(self) -> bool:
        return self._llm_factory().available

    def run(self, prompt: str, allowed_write_paths: set[str], allowed_edit_paths: set[str]) -> LocalCodeWriterResult:
        """`allowed_write_paths`: archivos NUEVOS que puede crear (el módulo
        del Specialist, su __init__.py de rama si hace falta, su test).
        `allowed_edit_paths`: archivos YA EXISTENTES que puede tocar con
        edit_file (los 4 de wiring). Cualquier otro path, en cualquiera de
        las dos tools, se rechaza antes de tocar el disco — el mismo
        alcance que SkillFactorySpecialist ya calculaba para el chequeo
        posterior por diff de git, ahora aplicado también en el momento."""
        llm = self._llm_factory()
        if not llm.available:
            raise RuntimeError("El modelo local configurado para la Skill Factory no está disponible.")

        test_run_count = 0
        num_tool_calls = 0

        def _read_file(i: dict) -> dict:
            path = self._repo_root / i["path"]
            if not path.exists():
                return {"error": f"'{i['path']}' no existe."}
            return {"content": path.read_text(encoding="utf-8")}

        def _write_file(i: dict) -> dict:
            rel = i["path"]
            if rel not in allowed_write_paths:
                return {
                    "error": f"'{rel}' no está en el alcance permitido para archivos nuevos: {sorted(allowed_write_paths)}"
                }
            full = self._repo_root / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(i["content"], encoding="utf-8")
            return {"status": "written", "path": rel}

        def _edit_file(i: dict) -> dict:
            rel = i["path"]
            if rel not in allowed_edit_paths:
                return {"error": f"'{rel}' no está en el alcance permitido para edición: {sorted(allowed_edit_paths)}"}
            full = self._repo_root / rel
            if not full.exists():
                return {"error": f"'{rel}' no existe."}
            content = full.read_text(encoding="utf-8")
            old = i["old_string"]
            count = content.count(old)
            if count == 0:
                return {"error": "old_string no aparece en el archivo — releelo con read_file antes de reintentar."}
            if count > 1:
                return {"error": f"old_string aparece {count} veces, no es único — dale más contexto para que sea exacto."}
            full.write_text(content.replace(old, i["new_string"], 1), encoding="utf-8")
            return {"status": "edited", "path": rel}

        def _run_tests(i: dict) -> dict:
            nonlocal test_run_count
            test_run_count += 1
            return self._run_tests_fn()

        handlers = {"read_file": _read_file, "write_file": _write_file, "edit_file": _edit_file, "run_tests": _run_tests}

        def tool_handler(name: str, tool_input: dict):
            nonlocal num_tool_calls
            num_tool_calls += 1
            handler = handlers.get(name)
            if not handler:
                return {"error": f"herramienta desconocida: {name}"}
            return handler(tool_input)

        tools = [
            {
                "name": "read_file",
                "description": "Lee el contenido real de un archivo del repo, dado su path relativo.",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            },
            {
                "name": "write_file",
                "description": (
                    "Escribe contenido completo en un archivo NUEVO tuyo (el módulo del Specialist o "
                    "su test) — solo funciona dentro del alcance de archivos nuevos permitido para "
                    "esta construcción. Podés llamarla más de una vez sobre el MISMO path para "
                    "corregir un error tuyo (sintaxis, lógica, lo que sea): dentro de tu propio "
                    "alcance de escritura, cada llamada reescribe el archivo entero con tu versión "
                    "más reciente — no hace falta (ni existe) un 'edit_file' para tus propios "
                    "archivos nuevos. edit_file es una herramienta aparte, solo para los 4 archivos "
                    "de wiring que YA EXISTÍAN antes de que arrancaras."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"],
                },
            },
            {
                "name": "edit_file",
                "description": (
                    "Reemplaza una porción exacta de un archivo YA EXISTENTE — old_string tiene que "
                    "aparecer una única vez, textual, en el archivo (si no es único, dale más "
                    "contexto alrededor). La única forma permitida de tocar un archivo existente — "
                    "nunca lo reescribas entero con write_file."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            },
            {
                "name": "run_tests",
                "description": "Corre la suite completa real de tests (.venv/bin/python -m pytest -q) y devuelve si pasó, con la salida real.",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

        start = time.monotonic()
        response = llm.generate(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_handler=tool_handler,
            max_tool_rounds=MAX_BUILD_TOOL_ROUNDS,
        )
        duration_seconds = time.monotonic() - start

        text = response.text or ""
        # test_run_count > 0 es la garantía real, no solo confiar en el
        # texto libre del modelo (ver docstring del módulo: ya vimos un
        # modelo local afirmar cosas que no habían pasado) — un "LISTO" sin
        # haber corrido run_tests ni una vez nunca cuenta como éxito acá.
        # Esto es además de, nunca en lugar de, la verificación
        # independiente real que SkillFactorySpecialist.build_skill() sigue
        # haciendo después (diff de git + su propia corrida de la suite).
        ok = test_run_count > 0 and "LISTO" in text.upper() and "NO PUDE" not in text.upper()
        return LocalCodeWriterResult(
            ok=ok,
            result_text=text,
            session_id=None,
            cost_usd=None,
            num_turns=num_tool_calls,
            raw={"duration_seconds": duration_seconds, "test_run_count": test_run_count},
        )
