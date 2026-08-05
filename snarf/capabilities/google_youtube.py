import threading

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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

    def get_video_captions(self, video_id: str) -> str | None:
        """Devuelve el texto real de la transcripción de `video_id`, o
        `None` si no hay ninguna disponible por esta vía. La API de YouTube
        solo permite descargar el contenido real de un caption track cuando
        el usuario autenticado es dueño del video (o tiene autorización
        explícita) — para un video de terceros, `captions().download()`
        devuelve un 403/`HttpError` real, no un caption vacío; se trata
        igual como "sin captions disponibles" (nunca se distingue "no
        existe" de "no autorizado" de cara al llamador, ambos son el mismo
        resultado real: no hay texto que usar por esta vía)."""
        try:
            tracks = self._client().captions().list(part="snippet", videoId=video_id).execute()
            items = tracks.get("items", [])
            if not items:
                return None
            caption_id = items[0]["id"]
            raw = self._client().captions().download(id=caption_id, tfmt="srt").execute()
            return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        except HttpError:
            return None
