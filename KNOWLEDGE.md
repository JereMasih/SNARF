# KNOWLEDGE

## Cómo Snarf accede a lo que sabe

**Versión:** 0.1
**Naturaleza:** describe el funcionamiento real implementado a la fecha, no una aspiración — mismo criterio que COGNITION.md. Se actualiza cada vez que cambia de forma material, y ese cambio queda registrado en CHANGELOG.md y, si es estructural, en un ADR.

---

# Regla central

Ningún Skill ni Especialista consulta archivos, APIs externas o el propio repositorio directamente para responder una pregunta de conocimiento — siempre pasa por la Knowledge Layer (`snarf/knowledge/`). Esto no es una preferencia de estilo: es lo que garantiza que toda respuesta con base en conocimiento indexado pase por el mismo pipeline de extracción/chunking/embeddings, con el mismo namespacing por usuario y dominio, en vez de que cada Skill nuevo reinvente su propio acceso a datos.

# El contrato `KnowledgeSource`

`snarf/knowledge/source.py` define el contrato que cualquier fuente de conocimiento nueva debe implementar — mismo espíritu que `Capability` (`snarf/capabilities/base.py`) y `Specialist` (`snarf/specialists/base.py`): sin identidad propia, inyectado por constructor, testeable con fixtures.

```python
class KnowledgeItem:  # dataclass: id, name, mime_type, modified_marker, extra_metadata
class KnowledgeSource(ABC):
    domain: str
    def iter_items(self) -> Iterator[KnowledgeItem]: ...
    def read_item(self, item: KnowledgeItem) -> bytes | str: ...
```

Fuentes reales hoy: `GoogleDriveKnowledgeSource` (`domain="personal"`), `NotionKnowledgeSource` (`domain="personal"`, activa por primera vez la Capacidad Notion que ADR 0075 dejó construida pero inactiva), `LocalRepoKnowledgeSource` (`domain="code"`, recorre `snarf/**/*.py`, `adr/*.md`, `tests/**/*.py` y los `.md` de la raíz de este mismo repositorio). Las subidas manuales (`POST /files/upload`) no son una `KnowledgeSource` enumerable — son push-based, un archivo a la vez — y se indexan directo vía `KnowledgeIndexer.index_local_text`, igual que hoy.

# Namespacing: dos mecanismos reales, cada uno con un trabajo distinto

Chroma (el vector store real detrás de todo esto, local, sin servidor — ver ADR 0028) ofrece dos primitivas de namespacing, y cada una hace un trabajo distinto:

- **`collection_name`** — uno por **dominio**. Dominios distintos tienen ciclos de vida de contenido distintos (reconstruir el índice de `code` nunca debe tocar `personal`).
- **filtro `where`** — para sub-alcance **dentro** de un dominio. Es exactamente el mecanismo que la Capacidad Proyectos ya usa para `project_id` (ADR 0045) — se reusa sin cambios, con más claves de metadata (`source: "drive"|"notion"|"upload"` dentro de `personal`).

# Estado real por dominio

| Dominio | Estado |
|---|---|
| `personal` | Real — Drive + Notion (una vez con `NOTION_API_KEY`) + subidas manuales + memoria episódica |
| `code` | Real — este mismo repositorio (código, ADRs, tests, docs de raíz) |
| `business` | Reservado — se puebla en cuanto la rama Finance (transacciones vía Sheet/CSV + recibos por visión) esté construida |
| `trading` | Reservado — sin fuente real todavía |
| `marketing` | Reservado — se puebla en cuanto la rama Community/Sales tenga datos reales que indexar |
| `finance` | Ver `business` — mismo dominio, nombre usado indistintamente en este documento hasta que se decida cuál queda |

Un dominio reservado nunca devuelve resultados inventados — `knowledge_search` sobre un dominio sin contenido indexado responde que no hay nada indexado, nunca completa el vacío con una respuesta genérica (Foundation, Principio VI).

# Cómo un Skill consulta la Knowledge Layer

Tools del Orchestrator: `knowledge_search(query, domain, top_k)`, `knowledge_index_start(domain, source, query=None)`, `knowledge_index_status(domain)`, y `codebase_search(query, top_k)` (wrapper fino, domain-locked a `code`). Un Specialist nuevo nunca abre un archivo directamente ni hace su propia llamada a un vector store — llama a estos tools, igual que cualquier otra Capacidad.

# Reportes como insumo, no solo como entregable

Todo Specialist que genere un reporte (por ejemplo, los de la rama Research) lo publica con `DocumentPublisher` y lo indexa vía `KnowledgeIndexer` en el dominio correspondiente — el reporte queda buscable por `knowledge_search` para cualquier Specialist posterior, incluida la Inteligencia Ejecutiva (ver COGNITION.md). Un reporte que no se indexa es un texto que se pierde en el chat; ese no es el patrón que este documento describe.

# Rama Memory (Fase I, ver plan de expansión "Inteligencia Ejecutiva") — cerrada por equivalencia real

De las 9 ramas del mapa de referencia (Memory/Productivity/Research/Content/Sales/Finance/Community/
Agency/Ops), Memory es la única que no suma código nuevo: cada pieza que pedía ya existe, con otro
nombre, construida en rondas anteriores de este mismo repo — no es una promesa, es la equivalencia
real, documento por documento:

| Pieza pedida | Equivalente real en Snarf |
|---|---|
| Obsidian Vault / wiki de conocimiento | Knowledge Layer generalizada (`snarf/knowledge/`, este documento) |
| `/projects active` (recordar en qué se está trabajando) | Proyectos (ADR 0045/0047/0054) — prompt, tareas, notas y conversaciones por proyecto |
| `CLAUDE.md` como prompt persistente de identidad | FOUNDATION.md/CONSTITUTION.md/CHARACTER.md (identidad real de Snarf) + `project.prompt` por Proyecto puntual |
| Memoria automática de conversaciones pasadas | `EpisodicMemory` (`data/episodic_memory.jsonl`, tools `list_conversations`/`get_conversation`/`search_memory`) |

Ninguna Capacidad ni Specialist nuevo se suma por esta rama — el trabajo real ya estaba hecho antes
de que este plan la nombrara.
