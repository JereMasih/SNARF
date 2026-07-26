from datetime import datetime, timezone

from googleapiclient.discovery import build

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth


class GoogleCalendar(Capability):
    name = "google_calendar"

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        self._service = None

    @property
    def available(self) -> bool:
        return self._auth.available

    def _client(self):
        if self._service is None:
            self._service = build("calendar", "v3", credentials=self._auth.credentials())
        return self._service

    def list_upcoming_events(self, max_results: int = 10) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        result = (
            self._client()
            .events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = []
        for e in result.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date"))
            events.append(
                {
                    "id": e["id"],
                    "summary": e.get("summary", "(sin título)"),
                    "start": start,
                    "location": e.get("location", ""),
                }
            )
        return events

    def create_event(
        self, summary: str, start_iso: str, end_iso: str, description: str | None = None, location: str | None = None
    ) -> dict:
        event = {"summary": summary, "start": {"dateTime": start_iso}, "end": {"dateTime": end_iso}}
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        return self._client().events().insert(calendarId="primary", body=event).execute()
