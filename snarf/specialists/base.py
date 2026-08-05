"""Contrato de Especialista Cognitivo (ver COGNITION.md/ADR 0003) — razona
sobre un dominio acotado, sin identidad propia, nunca habla directo con el
fundador.

Convención de Skill Framework (Fase G, ver plan de expansión "Inteligencia
Ejecutiva"): además del contrato `Specialist` de abajo, cada MÓDULO que
define una subclase real declara, a nivel de módulo, dos dicts —
`INPUT_SCHEMA`/`OUTPUT_SCHEMA`, misma forma JSON-Schema que
`orchestrator.TOOLS[i]["input_schema"]` (una sola convención de schema en el
repo, no dos). No es documentación decorativa: es lo que la Skill Factory
(Fase H) va a necesitar para generar y validar un módulo nuevo por máquina —
un humano leyendo un archivo de ~80 líneas no lo necesita, un generador de
código sí. `tests/test_specialist_schema_coverage.py` lo garantiza para
cada subclase real de `Specialist`, mismo protocolo de crecimiento que
`TOOL_TO_NODE`/`VERB_BY_SKILL` (ADR 0054): una subclase nueva sin sus dos
dicts hace fallar ese test.

El registro de un Skill-Specialist real sigue siendo el mismo de siempre —
1-3 tools nuevos en `orchestrator.TOOLS`/`_tool_handlers` + un nodo nuevo en
`brain.py` — nunca `REGISTRY` de abajo, que queda sin usar a propósito: un
dict a nivel de módulo no puede sostener más de una instancia por proceso
(cada `Orchestrator` construye su propia instancia con sus propias
Capacidades inyectadas, y varios tests reales instancian más de un
`Orchestrator` en el mismo proceso) — resucitarlo sería reintroducir ese
problema real, no resolverlo."""

from abc import ABC, abstractmethod


class Specialist(ABC):
    name: str
    domain: str

    @abstractmethod
    def handle(self, task: str, context: dict) -> str:
        ...


REGISTRY: dict[str, "Specialist"] = {}


def register(specialist: "Specialist") -> None:
    REGISTRY[specialist.name] = specialist
