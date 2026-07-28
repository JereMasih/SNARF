import json
import time
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_PATH = Path("data/episodic_memory.jsonl")


class EpisodicMemory:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(
        self,
        channel: str,
        user_input: str,
        response: str,
        conversation_id: str | None = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "channel": channel,
            "conversation_id": conversation_id,
            "input": user_input,
            "response": response,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _read_all(self) -> list[dict]:
        content = self.path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        return [json.loads(line) for line in content.splitlines()]

    def recent(self, n: int = 10, conversation_id: str | None = None) -> list[dict]:
        entries = self._read_all()
        if conversation_id is not None:
            entries = [e for e in entries if e.get("conversation_id") == conversation_id]
        return entries[-n:]

    def list_conversations(self) -> list[dict]:
        by_id: dict[str, dict] = {}
        for entry in self._read_all():
            cid = entry.get("conversation_id")
            if not cid:
                continue
            if cid not in by_id:
                by_id[cid] = {
                    "conversation_id": cid,
                    "title": entry["input"][:60],
                    "started_at": entry["timestamp"],
                    "last_activity": entry["timestamp"],
                }
            by_id[cid]["last_activity"] = entry["timestamp"]
        return sorted(by_id.values(), key=lambda c: c["last_activity"], reverse=True)

    def get_conversation(self, conversation_id: str) -> list[dict]:
        return [e for e in self._read_all() if e.get("conversation_id") == conversation_id]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        query_lower = query.lower().strip()
        if not query_lower:
            return []
        matches = [
            e
            for e in self._read_all()
            if query_lower in e.get("input", "").lower() or query_lower in e.get("response", "").lower()
        ]
        return matches[-limit:]

    def stats(self, activity_days: int = 14) -> dict:
        entries = self._read_all()
        timestamps = [e["timestamp"] for e in entries]
        conversation_ids = {e["conversation_id"] for e in entries if e.get("conversation_id")}

        today = datetime.now().date()
        buckets = {
            (today - timedelta(days=offset)).isoformat(): 0
            for offset in range(activity_days - 1, -1, -1)
        }
        for e in entries:
            day = datetime.fromtimestamp(e["timestamp"]).date().isoformat()
            if day in buckets:
                buckets[day] += 1

        return {
            "total_messages": len(entries),
            "total_conversations": len(conversation_ids),
            "oldest_timestamp": min(timestamps) if timestamps else None,
            "newest_timestamp": max(timestamps) if timestamps else None,
            "activity_by_day": [{"date": day, "count": count} for day, count in buckets.items()],
        }
