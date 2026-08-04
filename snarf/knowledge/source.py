from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class KnowledgeItem:
    """Un ítem indexable real de una fuente de conocimiento — nunca representa
    contenido que no exista de verdad en la fuente (Principio VI de
    Foundation). `modified_marker` decide si hace falta reprocesar (mismo rol
    que `modifiedTime` ya cumple para Drive en IndexManifest — para una
    fuente local es el mtime real del archivo, como string)."""

    id: str
    name: str
    mime_type: str
    modified_marker: str
    extra_metadata: dict = field(default_factory=dict)


class KnowledgeSource(ABC):
    """Contrato real que cualquier fuente de conocimiento nueva debe cumplir
    para conectarse a la Knowledge Layer (ver KNOWLEDGE.md) — mismo espíritu
    que Capability/Specialist: sin identidad propia, inyectada por
    constructor, testeable con fixtures. Nunca importa snarf.core ni
    snarf.runtime ni app.py (misma garantía de reusabilidad que
    tests/test_architecture_boundaries.py ya exige de Capabilities/
    Especialistas)."""

    domain: str

    @abstractmethod
    def iter_items(self) -> Iterator[KnowledgeItem]:
        """Enumera los ítems indexables reales de esta fuente, sin leer su
        contenido todavía (barato, para poder escanear antes de indexar —
        mismo patrón que DriveIndexer.scan())."""
        ...

    @abstractmethod
    def read_item(self, item: KnowledgeItem) -> str:
        """Devuelve el texto real de un ítem, ya extraído/decodificado y listo
        para chunkear. Una fuente que necesite extracción por tipo de archivo
        (PDF, imagen, audio) la resuelve acá adentro."""
        ...
