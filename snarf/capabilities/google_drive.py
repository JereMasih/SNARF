import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_retry import retry_with_fresh_client

GOOGLE_DOCS_EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class GoogleDrive(Capability):
    name = "google_drive"

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        self._service = None

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
            params["q"] = query
        result = self._client().files().list(**params).execute()
        return result.get("files", [])

    @retry_with_fresh_client
    def list_files_page(self, page_size: int = 200, query: str | None = None, page_token: str | None = None) -> dict:
        params = {
            "pageSize": page_size,
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size, webViewLink)",
        }
        if query:
            params["q"] = query
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
