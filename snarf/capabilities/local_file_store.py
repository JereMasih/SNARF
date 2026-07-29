from pathlib import Path

from snarf.capabilities.base import Capability


class LocalFileStore(Capability):
    """Guarda archivos en disco local, fuera de Drive — para contenido que el
    fundador no quiere (todavía, o nunca) subir a su Drive, pero que igual
    debe quedar disponible y buscable."""

    name = "local_file_store"

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    @property
    def available(self) -> bool:
        return True

    def save(self, name: str, content: bytes) -> Path:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / name
        path.write_bytes(content)
        return path
