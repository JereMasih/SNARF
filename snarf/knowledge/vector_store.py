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
        self._collection().add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

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

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        result = self._collection().query(query_embeddings=[query_embedding], n_results=top_k)
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
