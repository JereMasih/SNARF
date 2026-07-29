import json
import threading
import time
from pathlib import Path

from snarf.knowledge import chunking
from snarf.knowledge.extraction import categorize_mime
from snarf.knowledge.manifest import STATUS_ERROR, STATUS_INDEXED, STATUS_SKIPPED_UNSUPPORTED, IndexManifest

# Alias cómodo para acotar la indexación a lo que hoy sale gratis o casi
# gratis (extracción local/directa + embeddings casi seguro dentro del tier
# gratuito de Voyage): Google Docs/Sheets/Slides, PDF, Word/PowerPoint/Excel
# (.docx/.pptx/.xlsx) y texto plano. Deja afuera imagen, audio y video, que
# sí tienen costo real por archivo.
#
# 'mimeType = text/plain' (no 'contains text/'): en la corrida real del
# 2026-07-28 se comprobó que Drive clasifica como texto/* una cantidad
# enorme de código fuente y configuración (.py, .cfg, .xml, .map, .conf,
# .browser) de un backup de un entorno Python / proyecto Unity — 'contains'
# los traía a todos, contaminando el índice con ruido que no es conocimiento
# personal. Coincide además con el mimeType real que catalogamos para los
# .py compilados en ADR 0028 (categoría "other", no "text").
FREE_TIER_ALIAS = "free_tier"
FREE_TIER_DRIVE_QUERY = (
    "mimeType = 'application/vnd.google-apps.document' or "
    "mimeType = 'application/vnd.google-apps.spreadsheet' or "
    "mimeType = 'application/vnd.google-apps.presentation' or "
    "mimeType = 'application/pdf' or "
    "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
    "mimeType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation' or "
    "mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or "
    "mimeType = 'text/plain'"
)


def _resolve_query(query: str | None) -> str | None:
    return FREE_TIER_DRIVE_QUERY if query == FREE_TIER_ALIAS else query


class DriveIndexer:
    """Orquesta todo el pipeline de vectorización de Drive: enumera archivos,
    extrae contenido, embebe y guarda en el vector store, con progreso
    persistido para poder reanudar. Corre en un thread de background,
    arrancado siempre de forma explícita (ver ADR 0028)."""

    def __init__(self, drive, extractor, embeddings, vector_store, manifest_path: Path):
        self._drive = drive
        self._extractor = extractor
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._manifest = IndexManifest(manifest_path)
        self._data_dir = manifest_path.parent

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._status = self._idle_status()

    @staticmethod
    def _idle_status() -> dict:
        return {
            "running": False,
            "processed": 0,
            "indexed": 0,
            "skipped": 0,
            "errors": 0,
            "current_file": None,
            "started_at": None,
            "finished_at": None,
        }

    def scan(self, query: str | None = None) -> dict:
        query = _resolve_query(query)
        by_category: dict[str, dict] = {}
        total_files = 0
        total_bytes = 0
        for file in self._drive.iter_all_files(query=query):
            category = categorize_mime(file.get("mimeType", "") or "")
            size = int(file.get("size") or 0)
            bucket = by_category.setdefault(category, {"count": 0, "bytes": 0})
            bucket["count"] += 1
            bucket["bytes"] += size
            if category != "folder":
                total_files += 1
                total_bytes += size
        return {"total_files": total_files, "total_bytes": total_bytes, "by_category": by_category}

    def index_file(self, file: dict) -> dict:
        """Indexa un único archivo ya conocido (id + mimeType + modifiedTime),
        sin esperar a la próxima corrida de background — para archivos recién
        creados o subidos, que deben quedar buscables de inmediato."""
        data = self._manifest.load()
        self._process_file(data, file)
        self._manifest.save(data)
        return data.get(file["id"], {})

    def catalog_unsupported(self, query: str | None = None) -> dict:
        """Recorre el Drive y registra, para todo archivo de categoría 'other'
        (sin extractor hoy), su mimeType real y nombre — un catálogo de mera
        existencia, sin extraer contenido, para poder decidir con el fundador
        qué son y si vale la pena construirles soporte."""
        query = _resolve_query(query)
        by_mime_type: dict[str, dict] = {}
        files_registry = []
        for file in self._drive.iter_all_files(query=query):
            mime = file.get("mimeType", "") or ""
            if categorize_mime(mime) != "other":
                continue
            size = int(file.get("size") or 0)
            bucket = by_mime_type.setdefault(mime, {"count": 0, "bytes": 0, "examples": []})
            bucket["count"] += 1
            bucket["bytes"] += size
            if len(bucket["examples"]) < 8:
                bucket["examples"].append(file.get("name", ""))
            files_registry.append(
                {
                    "id": file["id"],
                    "name": file.get("name", ""),
                    "mimeType": mime,
                    "size": size,
                    "webViewLink": file.get("webViewLink", ""),
                }
            )

        catalog_path = self._data_dir / "unsupported_catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                {"generated_at": time.time(), "by_mime_type": by_mime_type, "files": files_registry},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"total_files": len(files_registry), "by_mime_type": by_mime_type, "catalog_path": str(catalog_path)}

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def manifest_summary(self) -> dict:
        """Cuenta de archivos por estado en el manifiesto ya persistido en
        disco — no dispara ningún escaneo nuevo. Base real para el nodo de
        Conocimiento del cerebro de Snarf (ver ADR pendiente de registrar)."""
        data = self._manifest.load()
        counts = {STATUS_INDEXED: 0, STATUS_ERROR: 0, STATUS_SKIPPED_UNSUPPORTED: 0}
        for entry in data.values():
            status = entry.get("status")
            if status in counts:
                counts[status] += 1
        return {
            "indexed": counts[STATUS_INDEXED],
            "error": counts[STATUS_ERROR],
            "skipped_unsupported": counts[STATUS_SKIPPED_UNSUPPORTED],
            "total": len(data),
        }

    def start(self, query: str | None = None) -> dict:
        query = _resolve_query(query)
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"status": "already_running", **self._status}
            self._stop_event = threading.Event()
            self._status = self._idle_status()
            self._status["running"] = True
            self._status["started_at"] = time.time()
            self._thread = threading.Thread(target=self._run, args=(query,), daemon=True)
            self._thread.start()
        return {"status": "started"}

    def stop(self) -> dict:
        self._stop_event.set()
        return {"status": "stopping"}

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        embedding = self._embeddings.embed([query], input_type="query")[0]
        return self._vector_store.search(embedding, top_k=top_k)

    def get_indexed_text(self, file_id: str) -> str:
        """Texto ya indexado de un archivo puntual (ej. la descripción que
        generó la visión al indexar una imagen recién subida) — para
        devolverlo de inmediato a la interfaz sin volver a pagar la
        extracción."""
        chunks = self._vector_store.get_by_file_id(file_id)
        return "\n\n".join(c["text"] for c in chunks)

    def index_local_text(self, item_id: str, name: str, text: str, extra_metadata: dict | None = None) -> dict:
        """Indexa texto que no viene de Drive (ej. un documento que el
        fundador eligió guardar localmente, no en su Drive) — ya se conoce el
        texto de origen, así que no hace falta extraerlo de ningún archivo."""
        chunks = chunking.chunk_text(text)
        if not chunks:
            return {"status": STATUS_SKIPPED_UNSUPPORTED, "chunk_count": 0}
        embeddings = self._embeddings.embed(chunks, input_type="document")
        ids = [f"{item_id}:{i}" for i in range(len(chunks))]
        metadatas = [
            {"file_id": item_id, "name": name, "location": "local", "chunk_index": i, **(extra_metadata or {})}
            for i in range(len(chunks))
        ]
        self._vector_store.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        return {"status": STATUS_INDEXED, "chunk_count": len(chunks)}

    def _run(self, query: str | None) -> None:
        data = self._manifest.load()
        try:
            for file in self._drive.iter_all_files(query=query):
                if self._stop_event.is_set():
                    break
                self._process_file(data, file)
                self._manifest.save(data)
        finally:
            with self._lock:
                self._status["running"] = False
                self._status["finished_at"] = time.time()

    def _process_file(self, data: dict, file: dict) -> None:
        file_id = file["id"]
        mime = file.get("mimeType", "") or ""
        modified_time = file.get("modifiedTime", "")
        category = categorize_mime(mime)

        with self._lock:
            self._status["current_file"] = file.get("name")

        if category == "folder":
            return
        if not self._manifest.needs_processing(data, file_id, modified_time):
            return

        try:
            result = self._extractor.extract(file)
        except Exception as exc:
            self._manifest.mark(data, file_id, modified_time, STATUS_ERROR, reason=str(exc))
            with self._lock:
                self._status["processed"] += 1
                self._status["errors"] += 1
            return

        if not result.ok:
            self._manifest.mark(data, file_id, modified_time, STATUS_SKIPPED_UNSUPPORTED, reason=result.skipped_reason)
            with self._lock:
                self._status["processed"] += 1
                self._status["skipped"] += 1
            return

        try:
            chunks = chunking.chunk_text(result.text)
            self._vector_store.delete_by_file_id(file_id)
            if chunks:
                embeddings = self._embeddings.embed(chunks, input_type="document")
                ids = [f"{file_id}:{i}" for i in range(len(chunks))]
                metadatas = [
                    {
                        "file_id": file_id,
                        "name": file.get("name", ""),
                        "webViewLink": file.get("webViewLink", ""),
                        "location": "drive",
                        "chunk_index": i,
                    }
                    for i in range(len(chunks))
                ]
                self._vector_store.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
            self._manifest.mark(data, file_id, modified_time, STATUS_INDEXED, chunk_count=len(chunks))
            with self._lock:
                self._status["processed"] += 1
                self._status["indexed"] += 1
        except Exception as exc:
            self._manifest.mark(data, file_id, modified_time, STATUS_ERROR, reason=str(exc))
            with self._lock:
                self._status["processed"] += 1
                self._status["errors"] += 1
