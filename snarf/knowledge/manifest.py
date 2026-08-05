import json
import os
import tempfile
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
        # Escritura atómica (bug real encontrado en vivo, 2026-08-05):
        # write_text() trunca el archivo y lo reescribe in-place — mientras
        # una indexación corre en background guardando seguido, cualquier
        # lector concurrente (ej. el dashboard, que hace polling de
        # manifest_summary()) puede atrapar el archivo a mitad de escritura
        # y recibir un JSON truncado (json.JSONDecodeError real, visto en
        # el log de producción). Escribir a un archivo temporal en el mismo
        # directorio y renombrarlo (os.replace, atómico en POSIX) hace que
        # cualquier lector siempre vea o el archivo viejo completo o el
        # nuevo completo, nunca una mezcla a medio escribir.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except BaseException:
            os.unlink(tmp_path)
            raise

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
