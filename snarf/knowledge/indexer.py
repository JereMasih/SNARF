import threading
import time
from pathlib import Path

from snarf.knowledge import chunking
from snarf.knowledge.manifest import STATUS_ERROR, STATUS_INDEXED, STATUS_SKIPPED_UNSUPPORTED, IndexManifest
from snarf.knowledge.source import KnowledgeItem, KnowledgeSource


class KnowledgeIndexer:
    """Motor de indexación genérico, agnóstico de fuente — mismo pipeline real
    que DriveIndexer (chunking -> embeddings -> vector store, progreso
    reanudable por manifiesto), pero contra cualquier KnowledgeSource en vez
    de estar acoplado a Drive. No reemplaza a DriveIndexer (sigue siendo el
    motor real del dominio 'personal', ver KNOWLEDGE.md) — es el camino nuevo
    para dominios sin la complejidad de extracción por mimetype que Drive sí
    tiene (imagen/audio/video)."""

    def __init__(self, source: KnowledgeSource, embeddings, vector_store, manifest_path: Path):
        self._source = source
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._manifest = IndexManifest(manifest_path)

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
            "current_item": None,
            "started_at": None,
            "finished_at": None,
        }

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def manifest_summary(self) -> dict:
        """Cuenta de ítems por estado en el manifiesto ya persistido en disco
        — no dispara ningún escaneo nuevo. Mismo rol que
        DriveIndexer.manifest_summary() para el nodo 'knowledge' del cerebro."""
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

    def start(self) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"status": "already_running", **self._status}
            self._stop_event = threading.Event()
            self._status = self._idle_status()
            self._status["running"] = True
            self._status["started_at"] = time.time()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return {"status": "started"}

    def stop(self) -> dict:
        self._stop_event.set()
        return {"status": "stopping"}

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        embedding = self._embeddings.embed([query], input_type="query")[0]
        return self._vector_store.search(embedding, top_k=top_k)

    def _run(self) -> None:
        data = self._manifest.load()
        try:
            for item in self._source.iter_items():
                if self._stop_event.is_set():
                    break
                self._process_item(data, item)
                self._manifest.save(data)
        finally:
            with self._lock:
                self._status["running"] = False
                self._status["finished_at"] = time.time()

    def _process_item(self, data: dict, item: KnowledgeItem) -> None:
        with self._lock:
            self._status["current_item"] = item.name

        if not self._manifest.needs_processing(data, item.id, item.modified_marker):
            return

        try:
            text = self._source.read_item(item)
        except Exception as exc:
            self._manifest.mark(data, item.id, item.modified_marker, STATUS_ERROR, reason=str(exc))
            with self._lock:
                self._status["processed"] += 1
                self._status["errors"] += 1
            return

        chunks = chunking.chunk_text(text)
        if not chunks:
            self._manifest.mark(
                data, item.id, item.modified_marker, STATUS_SKIPPED_UNSUPPORTED, reason="sin texto real"
            )
            with self._lock:
                self._status["processed"] += 1
                self._status["skipped"] += 1
            return

        try:
            embeddings = self._embeddings.embed(chunks, input_type="document")
            ids = [f"{item.id}:{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "file_id": item.id,
                    "name": item.name,
                    "domain": self._source.domain,
                    "chunk_index": i,
                    **item.extra_metadata,
                }
                for i in range(len(chunks))
            ]
            self._vector_store.delete_by_file_id(item.id)
            self._vector_store.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
            self._manifest.mark(data, item.id, item.modified_marker, STATUS_INDEXED, chunk_count=len(chunks))
            with self._lock:
                self._status["processed"] += 1
                self._status["indexed"] += 1
        except Exception as exc:
            self._manifest.mark(data, item.id, item.modified_marker, STATUS_ERROR, reason=str(exc))
            with self._lock:
                self._status["processed"] += 1
                self._status["errors"] += 1
