import json
import time
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_PATH = Path("data/episodic_memory.jsonl")
DEFAULT_PROJECT_LINKS_PATH = Path("data/conversation_projects.json")
DEFAULT_TITLES_PATH = Path("data/conversation_titles.json")


class EpisodicMemory:
    def __init__(
        self,
        path: Path = DEFAULT_PATH,
        project_links_path: Path = DEFAULT_PROJECT_LINKS_PATH,
        titles_path: Path = DEFAULT_TITLES_PATH,
    ):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        # Fuente de verdad de "a qué proyecto pertenece HOY esta conversación"
        # — separada a propósito del tag project_id por-entrada de append()
        # (que es histórico/auditoría: qué proyecto estaba vigente cuando se
        # escribió cada mensaje puntual, nunca se reescribe). Este mapeo sí
        # se sobreescribe con cada asignación/reasignación/desasignación.
        self._project_links_path = project_links_path
        self._project_links_path.parent.mkdir(parents=True, exist_ok=True)
        # Título generado automáticamente (LLM barato, ver
        # Orchestrator.generate_conversation_title) apenas ocurre el primer
        # intercambio real de una conversación — mismo criterio de archivo
        # aparte que project_links, nunca se deriva reescaneando el log.
        self._titles_path = titles_path
        self._titles_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_project_links(self) -> dict:
        if not self._project_links_path.exists():
            return {}
        content = self._project_links_path.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else {}

    def _write_project_links(self, links: dict) -> None:
        self._project_links_path.write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_conversation_project(self, conversation_id: str) -> str | None:
        link = self._read_project_links().get(conversation_id)
        return link.get("project_id") if link else None

    def assign_conversation(self, conversation_id: str, project_id: str) -> dict:
        links = self._read_project_links()
        from_project_id = links.get(conversation_id, {}).get("project_id")
        links[conversation_id] = {"project_id": project_id, "assigned_at": time.time()}
        self._write_project_links(links)
        return {"conversation_id": conversation_id, "from_project_id": from_project_id, "to_project_id": project_id}

    def unassign_conversation(self, conversation_id: str) -> dict:
        links = self._read_project_links()
        from_project_id = links.get(conversation_id, {}).get("project_id")
        links.pop(conversation_id, None)
        self._write_project_links(links)
        return {"conversation_id": conversation_id, "from_project_id": from_project_id, "to_project_id": None}

    def _read_titles(self) -> dict:
        if not self._titles_path.exists():
            return {}
        content = self._titles_path.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else {}

    def _write_titles(self, titles: dict) -> None:
        self._titles_path.write_text(json.dumps(titles, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_title(self, conversation_id: str, title: str) -> None:
        titles = self._read_titles()
        titles[conversation_id] = title
        self._write_titles(titles)

    def get_title(self, conversation_id: str) -> str | None:
        return self._read_titles().get(conversation_id)

    def append(
        self,
        channel: str,
        user_input: str,
        response: str,
        conversation_id: str | None = None,
        project_id: str | None = None,
        input_audio_id: str | None = None,
        speech: str | None = None,
        deliverable: str | None = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "channel": channel,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "input": user_input,
            "response": response,
            "input_audio_id": input_audio_id,
            "speech": speech,
            "deliverable": deliverable,
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

    def list_conversations(self, project_id: str | None = None, unassigned_only: bool = False) -> list[dict]:
        # Filtra por el mapeo vigente conversación→proyecto (fuente de
        # verdad real), no por el tag histórico project_id de cada entrada
        # del log — ese tag es auditoría de qué proyecto estaba vigente
        # cuando se escribió CADA mensaje, no "cuál es el proyecto actual".
        links = self._read_project_links()
        titles = self._read_titles()

        def current_project(cid: str) -> str | None:
            return links.get(cid, {}).get("project_id")

        by_id: dict[str, dict] = {}
        for entry in self._read_all():
            cid = entry.get("conversation_id")
            if not cid:
                continue
            if project_id is not None and current_project(cid) != project_id:
                continue
            if unassigned_only and current_project(cid) is not None:
                continue
            if cid not in by_id:
                by_id[cid] = {
                    "conversation_id": cid,
                    # El título generado automáticamente (ver
                    # Orchestrator.generate_conversation_title) reemplaza el
                    # substring crudo del primer mensaje apenas está listo —
                    # hasta entonces (o si el LLM no está disponible), se
                    # degrada a ese substring, nunca queda sin título.
                    "title": titles.get(cid) or entry["input"][:60],
                    "started_at": entry["timestamp"],
                    "last_activity": entry["timestamp"],
                }
            by_id[cid]["last_activity"] = entry["timestamp"]

        if project_id is not None:
            # Una conversación recién asignada, todavía sin ningún mensaje,
            # no tiene nada que escanear arriba — pero ya es una asociación
            # real y debe aparecer de una en la lista de ESE proyecto.
            for cid, link in links.items():
                if link.get("project_id") == project_id and cid not in by_id:
                    by_id[cid] = {
                        "conversation_id": cid,
                        "title": "(nueva conversación)",
                        "started_at": link["assigned_at"],
                        "last_activity": link["assigned_at"],
                    }

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
