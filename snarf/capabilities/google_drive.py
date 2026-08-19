import io
import re
import threading

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_retry import retry_with_fresh_client

GOOGLE_DOCS_EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

# Bug real encontrado en producción (ver activity_log.jsonl): el fundador/el
# propio Snarf pasan casi siempre texto libre como query ("vida es sueño",
# "Tommy") en vez de la sintaxis real de la API de Drive
# (`fullText contains 'vida es sueño'`) — la API devuelve un 400 real
# ("Invalid Value") cada vez, sin excepción. En vez de confiar en que quien
# llama siempre escriba sintaxis válida, se detecta si la query YA parece
# sintaxis real de Drive (tiene un operador reconocible) y, si no, se
# envuelve como búsqueda de texto completo real — degrada al caso común en
# vez de fallar. Una query construida internamente en este mismo archivo
# (ver get_or_create_folder, con `=`/`in`) sigue pasando intacta.
_DRIVE_QUERY_OPERATOR_RE = re.compile(r"\b(?:contains|in)\b|[=<>]")

# Bug real encontrado en producción (2026-08-19, ver activity_log.jsonl y ADR
# de esta ronda): la API de Google Docs puede estar deshabilitada en el
# proyecto de Google Cloud del fundador (distinto de tener el scope OAuth
# correcto — son dos cosas separadas) sin que nada lo avise hasta el primer
# intento real de leer/editar un documento. El HttpError crudo de Google es
# varios KB de JSON anidado repetido en cada intento — sin esto, Snarf (y
# cualquiera leyendo activity_log después) tiene que releer ese blob entero
# cada vez para encontrar la URL real de activación, en vez de un mensaje
# corto y accionable.
_ACTIVATION_URL_RE = re.compile(r"https://console\.developers\.google\.com/apis/api/[^\s'\"]+")


def _raise_clean_docs_api_error(exc: HttpError) -> None:
    message = str(exc)
    if "SERVICE_DISABLED" not in message:
        raise exc
    match = _ACTIVATION_URL_RE.search(message)
    url = match.group(0) if match else "https://console.cloud.google.com/apis/library/docs.googleapis.com"
    raise RuntimeError(
        "La API de Google Docs está deshabilitada en el proyecto de Google Cloud del fundador "
        f"(distinto del scope OAuth, ya autorizado) — hay que habilitarla acá: {url}. Puede tardar "
        "unos minutos en propagarse después de habilitarla."
    ) from exc


def _looks_like_drive_query_syntax(query: str) -> bool:
    return bool(_DRIVE_QUERY_OPERATOR_RE.search(query))


def _escape_query_literal(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def normalize_drive_query(query: str) -> str:
    if _looks_like_drive_query_syntax(query):
        return query
    return f"fullText contains '{_escape_query_literal(query)}'"


class GoogleDrive(Capability):
    name = "google_drive"

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        # FastAPI corre cada endpoint sync en un thread del threadpool — el
        # dashboard dispara varios widgets en paralelo, así que esta
        # Capacidad puede recibir llamadas concurrentes desde threads
        # distintos. Un solo `self._service` compartido corrompía la
        # conexión SSL/socket subyacente cuando dos threads la usaban al
        # mismo tiempo (confirmado reproduciendo el fallo real con
        # ThreadPoolExecutor: "[SSL] record layer failure"/"internal
        # error"/"length mismatch", todos síntomas clásicos de compartir un
        # socket TLS entre threads). `threading.local()` le da a cada thread
        # su propio cliente, cacheado igual dentro de ese thread.
        self._local = threading.local()

    @property
    def _service(self):
        return getattr(self._local_storage(), "service", None)

    @_service.setter
    def _service(self, value):
        self._local_storage().service = value

    def _local_storage(self) -> threading.local:
        # Defensivo ante construcción vía __new__ (como hacen los tests,
        # asignando _service directo sin pasar por __init__) — nunca falla
        # con AttributeError sin importar cómo se haya creado la instancia.
        local = self.__dict__.get("_local")
        if local is None:
            local = threading.local()
            self._local = local
        return local

    @property
    def available(self) -> bool:
        return self._auth.available

    def _client(self):
        if self._service is None:
            self._service = build("drive", "v3", credentials=self._auth.credentials())
        return self._service

    @retry_with_fresh_client
    def list_files(self, page_size: int = 50, query: str | None = None) -> list[dict]:
        params = {
            "pageSize": page_size,
            "fields": "files(id, name, mimeType, modifiedTime, size, webViewLink)",
        }
        if query:
            params["q"] = normalize_drive_query(query)
        result = self._client().files().list(**params).execute()
        return result.get("files", [])

    @retry_with_fresh_client
    def list_files_page(self, page_size: int = 200, query: str | None = None, page_token: str | None = None) -> dict:
        params = {
            "pageSize": page_size,
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size, webViewLink)",
        }
        if query:
            params["q"] = normalize_drive_query(query)
        if page_token:
            params["pageToken"] = page_token
        result = self._client().files().list(**params).execute()
        return {"files": result.get("files", []), "next_page_token": result.get("nextPageToken")}

    def iter_all_files(self, query: str | None = None, page_size: int = 200):
        """Recorre todas las páginas de un listado de Drive, sin cortar en la
        primera — necesario para enumerar un Drive grande (ver ADR 0028)."""
        page_token = None
        while True:
            page = self.list_files_page(page_size=page_size, query=query, page_token=page_token)
            yield from page["files"]
            page_token = page["next_page_token"]
            if not page_token:
                return

    @retry_with_fresh_client
    def read_file_text(self, file_id: str, mime_type: str) -> str:
        client = self._client()
        if mime_type in GOOGLE_DOCS_EXPORT_MIME:
            data = client.files().export(fileId=file_id, mimeType=GOOGLE_DOCS_EXPORT_MIME[mime_type]).execute()
        else:
            data = client.files().get_media(fileId=file_id).execute()
        return data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else str(data)

    @retry_with_fresh_client
    def read_file_bytes(self, file_id: str) -> bytes:
        return self._client().files().get_media(fileId=file_id).execute()

    @retry_with_fresh_client
    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        return self._client().files().create(body=body, fields="id, name").execute()

    def get_or_create_folder(self, name: str, parent_id: str | None = None) -> str:
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        existing = self.list_files(page_size=1, query=query)
        if existing:
            return existing[0]["id"]
        return self.create_folder(name, parent_id=parent_id)["id"]

    # Sin retry acá a propósito: MediaIoBaseUpload consume su stream de
    # bytes al ejecutar — reintentar con el mismo objeto subiría contenido
    # vacío en silencio en vez de fallar fuerte, mucho peor que el error real.
    def upload_file(
        self,
        name: str,
        content: bytes,
        mime_type: str,
        parent_id: str | None = None,
        convert_to: str | None = None,
    ) -> dict:
        """Sube bytes reales a Drive. Si `convert_to` es un mimeType nativo de
        Google (Docs/Sheets/Slides), Drive convierte el contenido subido al
        formato editable nativo — no hace falta la API de Google Docs aparte."""
        body: dict = {"name": name, "mimeType": convert_to or mime_type}
        if parent_id:
            body["parents"] = [parent_id]
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        return (
            self._client()
            .files()
            .create(body=body, media_body=media, fields="id, name, mimeType, modifiedTime, webViewLink")
            .execute()
        )

    @retry_with_fresh_client
    def move_file(self, file_id: str, new_parent_id: str) -> dict:
        client = self._client()
        file = client.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents", []))
        return (
            client.files()
            .update(fileId=file_id, addParents=new_parent_id, removeParents=previous_parents, fields="id, parents")
            .execute()
        )

    @retry_with_fresh_client
    def delete_file(self, file_id: str) -> None:
        self._client().files().delete(fileId=file_id).execute()

    @retry_with_fresh_client
    def rename_file(self, file_id: str, new_name: str) -> dict:
        return self._client().files().update(fileId=file_id, body={"name": new_name}, fields="id, name").execute()

    @retry_with_fresh_client
    def share_file(self, file_id: str, role: str = "reader", email: str | None = None) -> dict:
        """Da acceso real a un archivo real: a una persona puntual si se pasa
        `email`, o vía link público (`type: "anyone"`) si no. Cambia quién
        puede ver/editar algo fuera de la cuenta del fundador — el Orchestrator
        lo trata como acción de alto impacto, igual que borrar un archivo."""
        permission = {"type": "user", "role": role, "emailAddress": email} if email else {"type": "anyone", "role": role}
        return (
            self._client()
            .permissions()
            .create(fileId=file_id, body=permission, fields="id, type, role")
            .execute()
        )

    def _docs_client(self):
        # Sin cachear a propósito (a diferencia de _client()/self._service):
        # editar un documento existente es una acción puntual y de alto
        # impacto, no algo que se llame con la frecuencia de list_files/etc.
        # — el costo de reconstruir el cliente en cada llamada es marginal y
        # evita sumar un segundo cache thread-local + su propio manejo de
        # reintento en paralelo al de Drive. El scope 'drive' completo (ya en
        # SCOPES) alcanza para la API de Docs — no hace falta re-autenticar.
        return build("docs", "v1", credentials=self._auth.credentials())

    def read_document_text(self, file_id: str) -> str:
        """Texto plano real de un Google Doc, vía la API de Docs (no el
        export de Drive) — es lo que hace falta para poder mostrarle al
        fundador una vista previa de qué se va a reemplazar antes de tocar
        nada (ver replace_document_body)."""
        try:
            doc = self._docs_client().documents().get(documentId=file_id).execute()
        except HttpError as exc:
            _raise_clean_docs_api_error(exc)
        return "".join(
            run.get("textRun", {}).get("content", "")
            for element in doc.get("body", {}).get("content", [])
            for run in element.get("paragraph", {}).get("elements", [])
        )

    def replace_document_body(self, file_id: str, new_text: str) -> dict:
        """Reemplaza TODO el contenido de un Google Doc existente por
        new_text. Edición de alto impacto (Constitution Art. VII, ADR 0073)
        — el protocolo de confirmed vive en el handler del Orchestrator, no
        acá adentro, mismo criterio que delete_file/share_file."""
        docs = self._docs_client()
        try:
            doc = docs.documents().get(documentId=file_id).execute()
            end_index = doc["body"]["content"][-1]["endIndex"]
            requests = []
            if end_index > 1:
                requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index - 1}}})
            if new_text:
                requests.append({"insertText": {"location": {"index": 1}, "text": new_text}})
            if requests:
                docs.documents().batchUpdate(documentId=file_id, body={"requests": requests}).execute()
        except HttpError as exc:
            _raise_clean_docs_api_error(exc)
        return {"documentId": file_id, "status": "updated"}
