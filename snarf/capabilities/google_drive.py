from googleapiclient.discovery import build

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth

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

    def list_files(self, page_size: int = 50, query: str | None = None) -> list[dict]:
        params = {
            "pageSize": page_size,
            "fields": "files(id, name, mimeType, modifiedTime, size)",
        }
        if query:
            params["q"] = query
        result = self._client().files().list(**params).execute()
        return result.get("files", [])

    def read_file_text(self, file_id: str, mime_type: str) -> str:
        client = self._client()
        if mime_type in GOOGLE_DOCS_EXPORT_MIME:
            data = client.files().export(fileId=file_id, mimeType=GOOGLE_DOCS_EXPORT_MIME[mime_type]).execute()
        else:
            data = client.files().get_media(fileId=file_id).execute()
        return data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else str(data)
