import json
import time
import uuid
from pathlib import Path

BUG_REPORTS_DIR = Path("data/bug_reports")

# Cuántos turnos previos de la conversación activa se guardan como contexto
# real del reporte — alcanza para que Snarf, en una conversación futura
# distinta, entienda "de qué se trataba" sin tener que releer la
# conversación entera (ver ADR de esta ronda).
CONTEXT_RECENT_TURNS = 4

STATUSES = ("nuevo", "clasificado", "planificado", "en_progreso", "resuelto", "descartado")

TRIAGE_SYSTEM_PROMPT = (
    "Clasificás reportes de bugs reales de un usuario sobre Snarf, un asistente personal de IA. Dado "
    "el texto del reporte y el contexto de la conversación donde pasó, respondé ÚNICAMENTE un objeto "
    "JSON con exactamente estas claves: category (uno de ui, respuesta_incorrecta, "
    "integracion_externa, rendimiento, otro), severity (uno de baja, media, alta, critica) y plan "
    "(2-3 oraciones concretas de qué habría que investigar o corregir, basado solo en lo que dice el "
    "reporte y el contexto real — nunca inventes una causa que no esté sugerida por esos datos). "
    "Sin texto antes o después del JSON."
)


class BugReports:
    """Reportes de bugs del fundador (o de otro usuario, multi-usuario real
    — ver ADR 0137), un JSON por reporte (`data/bug_reports/{id}.json`),
    mismo patrón que `snarf/specialists/project_manager.py`: sin ORM,
    `_normalize()` defensivo en cada lectura. Cada reporte lleva capturado
    el `conversation_id` y las últimas turnos reales de esa conversación en
    el momento de reportar — así una conversación futura puede reconstruir
    el contexto original sin depender de que el fundador lo recuerde."""

    def __init__(self, memory_provider, user_id: str):
        # memory_provider: callable sin argumentos (no una instancia fija) —
        # mismo criterio que llm_factory en ProjectManager. Real, no solo
        # estilo: en tests, `orchestrator._memory` se reemplaza DESPUÉS de
        # construir el Orchestrator (ver tests/test_app.py::client) — una
        # referencia capturada en el constructor quedaría apuntando a la
        # memoria vieja para siempre.
        self._memory_provider = memory_provider
        self._user_id = user_id

    def _path(self, report_id: str) -> Path:
        return BUG_REPORTS_DIR / f"{report_id}.json"

    def _normalize(self, raw: dict, report_id: str) -> dict:
        status = raw.get("status")
        if status not in STATUSES:
            status = "nuevo"
        context = raw.get("context") if isinstance(raw.get("context"), dict) else {}
        return {
            "id": report_id,
            "user_id": str(raw.get("user_id", self._user_id)),
            "created_at": raw.get("created_at") if isinstance(raw.get("created_at"), (int, float)) else time.time(),
            "description": str(raw.get("description", "")),
            "status": status,
            "category": raw.get("category") if isinstance(raw.get("category"), str) else None,
            "severity": raw.get("severity") if isinstance(raw.get("severity"), str) else None,
            "plan": raw.get("plan") if isinstance(raw.get("plan"), str) else None,
            "resolution": raw.get("resolution") if isinstance(raw.get("resolution"), str) else None,
            "context": {
                "conversation_id": context.get("conversation_id"),
                "view": context.get("view"),
                "recent_turns": [
                    {
                        "input": str(t.get("input", "")),
                        "response": str(t.get("response", "")),
                        "timestamp": t.get("timestamp"),
                    }
                    for t in (context.get("recent_turns") or [])
                    if isinstance(t, dict)
                ],
            },
            "history": [
                {"timestamp": h.get("timestamp"), "status": h.get("status"), "note": str(h.get("note", ""))}
                for h in (raw.get("history") or [])
                if isinstance(h, dict) and h.get("status") in STATUSES
            ],
        }

    def _save(self, record: dict) -> dict:
        BUG_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._path(record["id"]).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def get(self, report_id: str) -> dict | None:
        path = self._path(report_id)
        if not path.exists():
            return None
        return self._normalize(json.loads(path.read_text(encoding="utf-8")), report_id)

    def list_reports(self, status: str | None = None) -> list[dict]:
        if not BUG_REPORTS_DIR.exists():
            return []
        reports = []
        for path in BUG_REPORTS_DIR.glob("*.json"):
            record = self._normalize(json.loads(path.read_text(encoding="utf-8")), path.stem)
            if status is None or record["status"] == status:
                reports.append(record)
        return sorted(reports, key=lambda r: r["created_at"], reverse=True)

    def create(self, description: str, conversation_id: str | None = None, view: str | None = None) -> dict:
        recent_turns = []
        if conversation_id:
            recent_turns = self._memory_provider().get_conversation(conversation_id, limit=CONTEXT_RECENT_TURNS)
        report_id = uuid.uuid4().hex[:12]
        record = self._normalize(
            {
                "user_id": self._user_id,
                "created_at": time.time(),
                "description": description,
                "status": "nuevo",
                "context": {"conversation_id": conversation_id, "view": view, "recent_turns": recent_turns},
                "history": [{"timestamp": time.time(), "status": "nuevo", "note": "reportado por el usuario"}],
            },
            report_id,
        )
        return self._save(record)

    def update_status(self, report_id: str, status: str, note: str = "") -> dict | None:
        if status not in STATUSES:
            raise ValueError(f"status inválido: {status!r} (válidos: {', '.join(STATUSES)})")
        record = self.get(report_id)
        if record is None:
            return None
        record["status"] = status
        record["history"].append({"timestamp": time.time(), "status": status, "note": note})
        return self._save(record)

    def apply_classification(self, report_id: str, category: str, severity: str, plan: str) -> dict | None:
        """Resultado real de la clasificación automática (ver
        _periodic_bug_triage_loop en app.py) — separado de update_status
        porque llena 3 campos a la vez y siempre mueve a 'planificado', a
        diferencia de un cambio de estado suelto."""
        record = self.get(report_id)
        if record is None:
            return None
        record["category"] = category
        record["severity"] = severity
        record["plan"] = plan
        record["status"] = "planificado"
        record["history"].append(
            {"timestamp": time.time(), "status": "planificado", "note": f"clasificado automáticamente: {category}/{severity}"}
        )
        return self._save(record)

    def resolve(self, report_id: str, resolution: str) -> dict | None:
        record = self.get(report_id)
        if record is None:
            return None
        record["resolution"] = resolution
        record["status"] = "resuelto"
        record["history"].append({"timestamp": time.time(), "status": "resuelto", "note": resolution})
        return self._save(record)
