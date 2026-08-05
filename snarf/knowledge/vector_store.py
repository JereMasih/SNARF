# chromadb tiene un tope real de items por llamada a add() (~5461 medido en
# esta instalación, varía por versión/config — chromadb no lo documenta como
# constante estable). Trocear en lotes seguros de antemano, mismo criterio
# que VoyageEmbeddings.embed() ya aplica para el límite de su propia API:
# un archivo con muchos chunks (ej. una transcripción de video larga) fallaba
# siempre con "ValueError: Batch size of N is greater than max batch size".
_ADD_BATCH_SIZE = 1000


class VectorStore:
    """Wrapper delgado sobre chromadb en modo persistente local (un
    directorio en disco, sin servidor) — embeddings siempre provistos por
    quien llama (Voyage), nunca calculados por chromadb. El cliente se arma
    recién en el primer uso real (igual que GoogleDrive._client()): construir
    esta clase no debe tocar disco ni importar chromadb de más."""

    def __init__(self, persist_directory: str, collection_name: str = "drive"):
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._collection_obj = None

    def _collection(self):
        if self._collection_obj is None:
            import chromadb

            client = chromadb.PersistentClient(path=self._persist_directory)
            self._collection_obj = client.get_or_create_collection(self._collection_name)
        return self._collection_obj

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
        if not ids:
            return
        collection = self._collection()
        for start in range(0, len(ids), _ADD_BATCH_SIZE):
            end = start + _ADD_BATCH_SIZE
            collection.add(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )

    def delete_by_file_id(self, file_id: str) -> None:
        self._collection().delete(where={"file_id": file_id})

    def count(self) -> int:
        return self._collection().count()

    def get_by_file_id(self, file_id: str) -> list[dict]:
        result = self._collection().get(where={"file_id": file_id})
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        return [{"id": ids[i], "text": documents[i], "metadata": metadatas[i]} for i in range(len(ids))]

    def search(self, query_embedding: list[float], top_k: int = 5, where: dict | None = None) -> list[dict]:
        result = self._collection().query(query_embeddings=[query_embedding], n_results=top_k, where=where)
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        documents = documents[0] if documents else []
        metadatas = metadatas[0] if metadatas else []
        distances = distances[0] if distances else []
        return [
            {"id": ids[i], "text": documents[i], "metadata": metadatas[i], "distance": distances[i]}
            for i in range(len(ids))
        ]
