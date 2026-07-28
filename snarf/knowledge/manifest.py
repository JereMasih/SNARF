import json
from pathlib import Path

STATUS_INDEXED = "indexed"
STATUS_SKIPPED_UNSUPPORTED = "skipped_unsupported"
STATUS_ERROR = "error"


class IndexManifest:
    """Progreso de indexación por archivo, persistido a disco. Permite
    reanudar un job interrumpido y re-indexar barato (saltea archivos sin
    cambios de modifiedTime) — ver ADR 0028."""

    def __init__(self, path: Path):
        self._path = path

    def load(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def needs_processing(self, data: dict, file_id: str, modified_time: str) -> bool:
        entry = data.get(file_id)
        if not entry:
            return True
        if entry.get("status") == STATUS_ERROR:
            # Un error (ej. falta VOYAGE_API_KEY, falla transitoria de red) no
            # es un resultado estable como "indexado" o "tipo no soportado" —
            # merece reintentarse en la próxima corrida aunque el archivo no
            # haya cambiado, en vez de quedar descartado para siempre.
            return True
        return entry.get("modifiedTime") != modified_time

    def mark(
        self,
        data: dict,
        file_id: str,
        modified_time: str,
        status: str,
        chunk_count: int = 0,
        reason: str | None = None,
    ) -> None:
        data[file_id] = {
            "modifiedTime": modified_time,
            "status": status,
            "chunk_count": chunk_count,
            "reason": reason,
        }
