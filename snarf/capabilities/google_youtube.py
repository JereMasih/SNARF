from googleapiclient.discovery import build

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_retry import retry_with_fresh_client


class GoogleYouTube(Capability):
    name = "google_youtube"

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        self._service = None

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
