from pathlib import Path
from typing import Iterator

from snarf.knowledge.source import KnowledgeItem, KnowledgeSource

# Solo lo que es realmente conocimiento operativo del propio repositorio —
# código, decisiones (ADRs), tests, documentación de raíz. Nunca datos
# generados (data/), nunca dependencias (.venv/, __pycache__), nunca
# secretos (credentials/) — ver Principio VI de Foundation: se indexa lo
# que es conocimiento real, no todo lo que hay en disco.
_GLOB_PATTERNS = ("snarf/**/*.py", "tests/**/*.py", "adr/*.md")
_ROOT_DOC_NAMES = (
    "FOUNDATION.md",
    "CONSTITUTION.md",
    "CHARACTER.md",
    "COGNITION.md",
    "KNOWLEDGE.md",
    "MASTER_MAP.md",
    "POLICY_HIGH_IMPACT_ACTIONS.md",
    "CLAUDE.md",
    "CHANGELOG.md",
)


class LocalRepoKnowledgeSource(KnowledgeSource):
    """Fuente de conocimiento sobre el propio repositorio de Snarf — código,
    ADRs, tests, documentación de raíz. Costo cero más allá de embeddings (a
    diferencia de Drive/Notion, no hay ninguna llamada de red para leer el
    contenido, ya vive en disco) — ver KNOWLEDGE.md, dominio 'code'. Es lo que
    hace que un rol como el CTO de Inteligencia Ejecutiva tenga una fuente
    100% real desde el día uno."""

    domain = "code"

    def __init__(self, root: Path | str = "."):
        self._root = Path(root)

    def iter_items(self) -> Iterator[KnowledgeItem]:
        seen: set[str] = set()
        paths: list[Path] = []
        for pattern in _GLOB_PATTERNS:
            paths.extend(self._root.glob(pattern))
        for name in _ROOT_DOC_NAMES:
            candidate = self._root / name
            if candidate.exists():
                paths.append(candidate)

        for path in paths:
            if not path.is_file():
                continue
            rel = str(path.relative_to(self._root))
            if rel in seen:
                continue
            seen.add(rel)
            stat = path.stat()
            mime_type = "text/x-python" if path.suffix == ".py" else "text/markdown"
            yield KnowledgeItem(
                id=rel,
                name=rel,
                mime_type=mime_type,
                modified_marker=str(stat.st_mtime),
                extra_metadata={"path": rel},
            )

    def read_item(self, item: KnowledgeItem) -> str:
        return (self._root / item.id).read_text(encoding="utf-8")
