from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from snarf.capabilities.base import Capability
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_retry import retry_once_with_fresh_client


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

    @retry_once_with_fresh_client
    def list_calendars(self) -> list[dict]:
        result = self._client().calendarList().list().execute()
        return [
            {"id": c["id"], "summary": c.get("summary", ""), "primary": c.get("primary", False)}
            for c in result.get("items", [])
        ]

    def create_calendar(self, summary: str, description: str | None = None) -> dict:
        body = {"summary": summary}
        if description:
            body["description"] = description
        return self._client().calendars().insert(body=body).execute()

    def delete_calendar(self, calendar_id: str) -> None:
        self._client().calendars().delete(calendarId=calendar_id).execute()

    @retry_once_with_fresh_client
    def list_upcoming_events(self, max_results: int = 10, calendar_id: str = "primary") -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        result = (
            self._client()
            .events()
            .list(
                calendarId=calendar_id,
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
                    "htmlLink": e.get("htmlLink", ""),
                }
            )
        return events

    def create_event(
        self,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str | None = None,
        location: str | None = None,
        calendar_id: str = "primary",
    ) -> dict:
        event = {"summary": summary, "start": {"dateTime": start_iso}, "end": {"dateTime": end_iso}}
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        return self._client().events().insert(calendarId=calendar_id, body=event).execute()

    @retry_once_with_fresh_client
    def search_events(self, query: str, calendar_id: str = "primary", max_results: int = 10) -> list[dict]:
        """Busca eventos por texto, sin restricción de fecha (incluye pasados y futuros)."""
        time_min = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        result = (
            self._client()
            .events()
            .list(
                calendarId=calendar_id,
                q=query,
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = []
        for e in result.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date"))
            events.append({"id": e["id"], "summary": e.get("summary", "(sin título)"), "start": start})
        return events

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        self._client().events().delete(calendarId=calendar_id, eventId=event_id).execute()

    def move_event(self, event_id: str, source_calendar_id: str, destination_calendar_id: str) -> dict:
        return (
            self._client()
            .events()
            .move(calendarId=source_calendar_id, eventId=event_id, destination=destination_calendar_id)
            .execute()
        )
