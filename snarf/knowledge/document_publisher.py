import uuid

# (mimeType con el que se sube el contenido, mimeType nativo de Google al
# que Drive debe convertirlo — None si el archivo se guarda tal cual).
FORMAT_MIME = {
    "markdown": ("text/markdown", None),
    "pdf": ("application/pdf", None),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", None),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None),
    "google_doc": ("text/plain", "application/vnd.google-apps.document"),
    "google_sheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.spreadsheet",
    ),
    "google_slide": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.google-apps.presentation",
    ),
}
FORMAT_EXTENSION = {"markdown": ".md", "pdf": ".pdf", "pptx": ".pptx", "xlsx": ".xlsx"}

DOCUMENT_FORMATS = {"markdown", "pdf", "google_doc"}
SPREADSHEET_FORMATS = {"xlsx", "google_sheet"}
PRESENTATION_FORMATS = {"pptx", "google_slide"}
# Los formatos nativos de Google solo existen por conversión al subir a
# Drive — no tienen sentido como archivo local.
GOOGLE_NATIVE_FORMATS = {"google_doc", "google_sheet", "google_slide"}

# Anidada bajo una única carpeta raíz "Snarf" en Drive (separada de las
# carpetas propias del fundador) desde que se sumó "Proyectos" — antes vivía
# suelta como "Snarf - Archivos" en la raíz del Drive.
ROOT_FOLDER_NAME = "Snarf"
FOLDER_NAME = "Archivos"


def _flatten_rows(rows: list[list]) -> str:
    return "\n".join(" | ".join(str(cell) for cell in row) for row in rows)


def _flatten_slides(slides: list[dict]) -> str:
    return "\n\n".join(f"{s.get('title', '')}\n{s.get('body', '')}" for s in slides)


# 'device': se guarda transitoriamente en el servidor solo para poder
# servir la descarga — el navegador la recibe con su diálogo nativo de
# "Guardar como" (el propio sistema operativo del fundador o del usuario
# decide cómo se ve, Snarf no construye nada específico por plataforma).
# 'server': lo mismo, pero sin link de descarga — pensado para que el
# fundador use el disco del propio servidor como carpeta de trabajo. Nadie
# más que el fundador puede pedir este destino (ver `allow_server_storage`).
LOCAL_DESTINATIONS = {"device", "server"}


class DocumentPublisher:
    """Orquesta la creación de archivos reales, en el destino que elija el
    fundador: Drive (real, opcionalmente convertido a un formato nativo de
    Google), el dispositivo de quien pregunta (vía descarga del navegador,
    'device') o el disco del propio servidor ('server', solo fundador). En
    los tres casos queda indexado de inmediato. Recibe todo por inyección —
    sin importar snarf.core ni snarf.runtime (ver ADR 0026)."""

    def __init__(self, builder, drive, indexer, local_store, user_id: str, allow_server_storage: bool = False):
        self._builder = builder
        self._drive = drive
        self._indexer = indexer
        self._local_store = local_store
        self._user_id = user_id
        self._allow_server_storage = allow_server_storage
        self._folder_id = None

    def folder_id(self) -> str:
        """Id de la carpeta 'Snarf/Archivos' del Drive del fundador, donde
        viven tanto los archivos que Snarf genera como los que el fundador le
        sube — se crea la primera vez que hace falta, se cachea después."""
        if self._folder_id is None:
            root_id = self._drive.get_or_create_folder(ROOT_FOLDER_NAME)
            self._folder_id = self._drive.get_or_create_folder(FOLDER_NAME, parent_id=root_id)
        return self._folder_id

    def _publish(self, name: str, content_bytes: bytes, format_key: str, destination: str, index_text: str) -> dict:
        if destination in LOCAL_DESTINATIONS:
            if destination == "server" and not self._allow_server_storage:
                raise ValueError("el destino 'server' solo está disponible para el fundador")
            if format_key in GOOGLE_NATIVE_FORMATS:
                raise ValueError(f"'{format_key}' no existe fuera de Drive, solo por conversión al subir")
            path = self._local_store.save(name, content_bytes)
            item_id = f"{destination}:{uuid.uuid4().hex}"
            index_result = self._indexer.index_local_text(
                item_id, name, index_text, extra_metadata={"path": str(path), "location": destination}
            )
            result = {
                "id": item_id,
                "name": name,
                "path": str(path),
                "webViewLink": None,
                "indexed": index_result["status"] == "indexed",
                "location": destination,
            }
            if destination == "device":
                result["download_url"] = f"/files/local/{self._user_id}/{name}"
            return result

        upload_mime, convert_to = FORMAT_MIME[format_key]
        created = self._drive.upload_file(name, content_bytes, upload_mime, parent_id=self.folder_id(), convert_to=convert_to)
        try:
            index_result = self._indexer.index_file(created)
            indexed = index_result.get("status") == "indexed"
        except Exception:
            indexed = False
        return {
            "id": created["id"],
            "name": created["name"],
            "webViewLink": created.get("webViewLink"),
            "indexed": indexed,
            "location": "drive",
        }

    def create_document(self, title: str, content: str, format: str = "markdown", destination: str = "drive") -> dict:
        if format not in DOCUMENT_FORMATS:
            raise ValueError(f"formato no soportado para documento: {format}")
        if format == "pdf":
            content_bytes = self._builder.build_pdf(title, content)
            filename = f"{title}.pdf"
        elif format == "markdown":
            content_bytes = self._builder.build_markdown(title, content)
            filename = f"{title}.md"
        else:  # google_doc
            content_bytes = content.encode("utf-8")
            filename = title
        return self._publish(filename, content_bytes, format, destination, content)

    def create_spreadsheet(self, title: str, rows: list[list], format: str = "xlsx", destination: str = "drive") -> dict:
        if format not in SPREADSHEET_FORMATS:
            raise ValueError(f"formato no soportado para planilla: {format}")
        content_bytes = self._builder.build_xlsx(title, rows)
        filename = title if format == "google_sheet" else f"{title}.xlsx"
        return self._publish(filename, content_bytes, format, destination, _flatten_rows(rows))

    def create_presentation(self, title: str, slides: list[dict], format: str = "pptx", destination: str = "drive") -> dict:
        if format not in PRESENTATION_FORMATS:
            raise ValueError(f"formato no soportado para presentación: {format}")
        content_bytes = self._builder.build_pptx(title, slides)
        filename = title if format == "google_slide" else f"{title}.pptx"
        return self._publish(filename, content_bytes, format, destination, _flatten_slides(slides))
