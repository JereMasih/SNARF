import threading

from googleapiclient.discovery import build

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_retry import retry_with_fresh_client


class GoogleYouTube(Capability):
    name = "google_youtube"

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        # Ver el comentario equivalente en GoogleDrive: un solo `self._service`
        # compartido entre threads del threadpool de FastAPI corrompía la
        # conexión SSL/socket subyacente bajo llamadas concurrentes reales
        # (confirmado reproduciendo el fallo con ThreadPoolExecutor).
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
            self._service = build("youtube", "v3", credentials=self._auth.credentials())
        return self._service

    @retry_with_fresh_client
    def list_subscriptions(self, max_results: int = 25) -> list[dict]:
        result = self._client().subscriptions().list(part="snippet", mine=True, maxResults=max_results).execute()
        return [
            {
                "channel": item["snippet"]["title"],
                "channel_id": item["snippet"]["resourceId"]["channelId"],
            }
            for item in result.get("items", [])
        ]

    @retry_with_fresh_client
    def list_liked_videos(self, max_results: int = 25) -> list[dict]:
        result = self._client().videos().list(part="snippet", myRating="like", maxResults=max_results).execute()
        return [
            {"title": item["snippet"]["title"], "channel": item["snippet"]["channelTitle"]}
            for item in result.get("items", [])
        ]
