import base64
import threading
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_retry import retry_with_fresh_client


class GoogleGmail(Capability):
    name = "google_gmail"

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        # Ver el comentario equivalente en GoogleDrive: FastAPI corre cada
        # endpoint sync en un thread del threadpool, y el dashboard dispara
        # varios widgets en paralelo — un solo `self._service` compartido
        # entre threads corrompía la conexión SSL/socket subyacente
        # (reproducido real: "[SSL] record layer failure" bajo llamadas
        # concurrentes). `threading.local()` le da a cada thread su propio
        # cliente.
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
            self._service = build("gmail", "v1", credentials=self._auth.credentials())
        return self._service

    @retry_with_fresh_client
    def list_messages(self, max_results: int = 10, query: str | None = None) -> list[dict]:
        params = {"userId": "me", "maxResults": max_results}
        if query:
            params["q"] = query
        result = self._client().users().messages().list(**params).execute()
        summaries = []
        for m in result.get("messages", []):
            msg = (
                self._client()
                .users()
                .messages()
                .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            summaries.append(
                {
                    "id": m["id"],
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                }
            )
        return summaries

    @retry_with_fresh_client
    def read_message(self, message_id: str) -> dict:
        msg = self._client().users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return {
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "body": self._extract_body(msg["payload"]),
        }

    def _extract_body(self, payload: dict) -> str:
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        for part in payload.get("parts", []) or []:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
        for part in payload.get("parts", []) or []:
            text = self._extract_body(part)
            if text:
                return text
        return ""

    def send_message(self, to: str, subject: str, body: str) -> dict:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return self._client().users().messages().send(userId="me", body={"raw": raw}).execute()

    @retry_with_fresh_client
    def list_labels(self) -> list[dict]:
        result = self._client().users().labels().list(userId="me").execute()
        return [{"id": l["id"], "name": l["name"], "type": l.get("type", "")} for l in result.get("labels", [])]

    def create_label(self, name: str) -> dict:
        body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        return self._client().users().labels().create(userId="me", body=body).execute()

    def delete_label(self, label_id: str) -> None:
        self._client().users().labels().delete(userId="me", id=label_id).execute()

    def modify_message_labels(
        self, message_id: str, add_label_ids: list[str] | None = None, remove_label_ids: list[str] | None = None
    ) -> dict:
        body = {"addLabelIds": add_label_ids or [], "removeLabelIds": remove_label_ids or []}
        return self._client().users().messages().modify(userId="me", id=message_id, body=body).execute()
