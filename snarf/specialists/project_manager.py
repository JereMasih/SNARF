import json
import re
import time
import uuid
from pathlib import Path

PROJECTS_DIR = Path("data/projects")
ROOT_FOLDER_NAME = "Snarf"
PROJECTS_FOLDER_NAME = "Proyectos"
# ≈1600-2000 tokens — presupuesto de instrucciones de proyecto largo (el
# fundador trae prompts maestros de referencia de ~1500+ palabras) sin
# inflar demasiado cada turno de las conversaciones asociadas. El frontend
# usa el mismo número como maxlength del textarea (duplicado con comentario
# cruzado, mismo precedente que GMAIL_MAX_RESULTS_CHOICES en dashboard_prefs.py).
PROJECT_PROMPT_MAX_LENGTH = 8000

SUBFOLDER_SUGGESTION_SYSTEM_PROMPT = (
    "Proponé de 2 a 4 nombres cortos de subcarpeta (en español) para organizar los archivos "
    "de un proyecto personal, dado su nombre. Respondé SOLO una lista separada por comas, "
    "sin numeración ni explicación."
)

SUMMARY_SYSTEM_PROMPT = (
    "Sos un asistente que escribe resúmenes breves, profesionales y útiles del estado actual "
    "de un proyecto personal, a partir únicamente de los datos reales que se te dan — nunca "
    "inventes tareas, notas o avances que no estén en esa información. Escribí en español, en "
    "3 a 5 oraciones, priorizando qué está pendiente y qué es lo más relevante ahora mismo."
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "proyecto"


class ProjectManager:
    """Gestiona los "Proyectos" de Snarf: cada uno es una carpeta de Drive +
    un prompt propio + listas de tareas y notas, persistidas en su propio
    JSON (`data/projects/{id}.json`). No es un Specialist (su contrato de un
    solo `handle()` no encaja con un manejador de varias operaciones CRUD),
    pero vive en `snarf/specialists/` por el mismo motivo que
    `GmailDigestSpecialist`: compone una Capacidad (Drive) más un llamado a
    LLM, sin importar `snarf.core`/`snarf.runtime` (ver ADR 0026)."""

    def __init__(
        self,
        drive,
        indexer,
        llm_factory,
        user_id: str,
        subfolder_system_prompt_provider=None,
        summary_system_prompt_provider=None,
        projects_dir: Path = PROJECTS_DIR,
        second_brain=None,
    ):
        # llm_factory: callable sin argumentos, ver el mismo criterio
        # documentado en GmailDigestSpecialist.__init__ — nunca una
        # instancia fija, para que el ruteo de LLM configurado en caliente
        # se refleje sin reiniciar el servidor. Mismo criterio para los dos
        # providers de prompt (Prompt Registry, ADR 0141) — inyectados por
        # quien construye este Specialist, nunca importados acá (ADR 0026).
        self._drive = drive
        self._indexer = indexer
        self._llm_factory = llm_factory
        self._user_id = user_id
        # Bug real corregido en ADR 0183 (mismo patrón que ADR 0137 ya
        # aplicó a EpisodicMemory): sin este parámetro, dos Orchestrator de
        # dos usuarios distintos habrían compartido los mismos archivos de
        # proyecto — PROJECTS_DIR era una constante de módulo fija, sin
        # relación con qué user_id la usaba. DEFAULT_USER_ID sigue en
        # PROJECTS_DIR a propósito (compatibilidad con datos reales ya en
        # disco); cualquier otro user_id recibe su propia carpeta.
        self._projects_dir = projects_dir
        # SecondBrainManager (ver ADR 0184), opcional — un Proyecto de Snarf
        # siempre se puede crear sin Notion. Cuando está presente Y el
        # fundador ya tiene el Second Brain conectado, create() también crea
        # la fila real en su database de Proyectos y guarda el vínculo.
        self._second_brain = second_brain
        self._root_folder_id: str | None = None
        self._subfolder_system_prompt_provider = subfolder_system_prompt_provider or (
            lambda: SUBFOLDER_SUGGESTION_SYSTEM_PROMPT
        )
        self._summary_system_prompt_provider = summary_system_prompt_provider or (lambda: SUMMARY_SYSTEM_PROMPT)

    def _root_folder(self) -> str:
        # Mismo patrón lazy-cached que DocumentPublisher.folder_id(): la
        # carpeta raíz "Snarf" ya existe (compartida con Archivos) — acá solo
        # hace falta la subcarpeta "Proyectos" adentro.
        if self._root_folder_id is None:
            snarf_root = self._drive.get_or_create_folder(ROOT_FOLDER_NAME)
            self._root_folder_id = self._drive.get_or_create_folder(PROJECTS_FOLDER_NAME, parent_id=snarf_root)
        return self._root_folder_id

    def _path(self, project_id: str) -> Path:
        return self._projects_dir / f"{project_id}.json"

    def _normalize(self, raw: dict, project_id: str) -> dict:
        # Misma disciplina que dashboard_prefs.py: nunca confiar en lo que
        # hay en disco — tipos, claves faltantes, elementos corruptos.
        summary_generated_at = raw.get("summary_generated_at")
        if not isinstance(summary_generated_at, (int, float)) or isinstance(summary_generated_at, bool):
            summary_generated_at = None
        return {
            "id": project_id,
            "name": str(raw.get("name", "")).strip() or "(sin nombre)",
            "prompt": str(raw.get("prompt", ""))[:PROJECT_PROMPT_MAX_LENGTH],
            "summary": str(raw.get("summary", "")),
            "summary_generated_at": summary_generated_at,
            "drive_folder_id": raw.get("drive_folder_id"),
            # Espejo Snarf↔Notion (ADR 0184) — id de página real de Notion
            # dentro de la database de Proyectos mapeada del Second Brain, o
            # None si este Proyecto nunca se vinculó (proyectos viejos, o
            # Second Brain no conectado al crearlo).
            "notion_project_page_id": raw.get("notion_project_page_id")
            if isinstance(raw.get("notion_project_page_id"), str)
            else None,
            "subfolders": {
                str(k): str(v) for k, v in (raw.get("subfolders") or {}).items() if isinstance(v, str)
            },
            "created_at": raw.get("created_at") if isinstance(raw.get("created_at"), (int, float)) else time.time(),
            "tasks": [
                {"id": str(t["id"]), "text": str(t.get("text", "")), "done": bool(t.get("done", False))}
                for t in (raw.get("tasks") or [])
                if isinstance(t, dict) and t.get("id")
            ],
            "notes": [
                {"id": str(n["id"]), "text": str(n.get("text", "")), "created_at": n.get("created_at", 0)}
                for n in (raw.get("notes") or [])
                if isinstance(n, dict) and n.get("id")
            ],
        }

    def get(self, project_id: str) -> dict | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        return self._normalize(json.loads(path.read_text(encoding="utf-8")), project_id)

    def _save(self, record: dict) -> dict:
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        self._path(record["id"]).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def list_projects(self) -> list[dict]:
        if not self._projects_dir.exists():
            return []
        summaries = []
        for path in sorted(self._projects_dir.glob("*.json")):
            record = self._normalize(json.loads(path.read_text(encoding="utf-8")), path.stem)
            summaries.append(
                {
                    "id": record["id"],
                    "name": record["name"],
                    "task_count": len(record["tasks"]),
                    "note_count": len(record["notes"]),
                    "created_at": record["created_at"],
                }
            )
        return sorted(summaries, key=lambda p: p["created_at"], reverse=True)

    def _suggest_subfolders(self, name: str) -> list[str]:
        # Degradación elegante, mismo espíritu que GmailDigestSpecialist: sin
        # LLM disponible o si falla, no se rompe la creación del proyecto —
        # cae a una sola subcarpeta genérica.
        llm = self._llm_factory()
        if not llm.available:
            return ["Archivos"]
        try:
            response = llm.generate(
                system=self._subfolder_system_prompt_provider(), messages=[{"role": "user", "content": name}]
            )
            names = [n.strip() for n in response.text.split(",") if n.strip()][:4]
            return names or ["Archivos"]
        except Exception:
            return ["Archivos"]

    def create(self, name: str) -> dict:
        short_id = uuid.uuid4().hex[:8]
        project_id = f"{_slugify(name)}-{short_id}"
        # La carpeta de Drive lleva el sufijo también (no solo el registro
        # local) — get_or_create_folder busca por nombre literal, así que dos
        # proyectos con el mismo nombre visible (ej. borrado y recreado)
        # colisionarían en la misma carpeta real si el nombre de carpeta
        # fuera el nombre a secas.
        folder_name = f"{name} ({short_id})"
        drive_folder_id = self._drive.get_or_create_folder(folder_name, parent_id=self._root_folder())

        subfolders = self._suggest_subfolders(name)
        subfolder_ids = {sub: self._drive.get_or_create_folder(sub, parent_id=drive_folder_id) for sub in subfolders}

        notion_project_page_id = self._second_brain.create_project_row(name) if self._second_brain else None

        record = self._normalize(
            {
                "name": name,
                "prompt": "",
                "drive_folder_id": drive_folder_id,
                "subfolders": subfolder_ids,
                "created_at": time.time(),
                "tasks": [],
                "notes": [],
                "notion_project_page_id": notion_project_page_id,
            },
            project_id,
        )
        return self._save(record)

    def find_by_notion_page_id(self, notion_page_id: str) -> dict | None:
        """Busca el Proyecto de Snarf vinculado a una página real de Notion
        (ver ADR 0187 — usado por la UI del Second Brain para saber, al
        mostrar los Proyectos de un Área, cuál de ellos ya tiene su
        'hermano' en Snarf con conversaciones/tareas/notas propias). Recorre
        los proyectos locales de este usuario — la cantidad real es chica,
        no amerita un índice aparte todavía."""
        if not self._projects_dir.exists():
            return None
        for path in sorted(self._projects_dir.glob("*.json")):
            record = self._normalize(json.loads(path.read_text(encoding="utf-8")), path.stem)
            if record["notion_project_page_id"] == notion_page_id:
                return record
        return None

    def set_notion_link(self, project_id: str, notion_page_id: str | None) -> dict | None:
        """Vincula (o desvincula, con notion_page_id=None) un Proyecto ya
        existente a una página real de Notion — usado tanto por el camino
        explícito (second_brain_link_project, validado antes de llamar acá)
        como potencialmente para desvincular. No valida nada por su cuenta:
        quien llama (el handler del Orchestrator) ya confirmó que la página
        existe."""
        record = self.get(project_id)
        if record is None:
            return None
        record["notion_project_page_id"] = notion_page_id
        return self._save(record)

    def set_prompt(self, project_id: str, prompt: str) -> dict | None:
        record = self.get(project_id)
        if record is None:
            return None
        record["prompt"] = prompt[:PROJECT_PROMPT_MAX_LENGTH]
        return self._save(record)

    def add_task(self, project_id: str, text: str) -> dict | None:
        record = self.get(project_id)
        if record is None:
            return None
        record["tasks"].append({"id": uuid.uuid4().hex[:12], "text": text, "done": False})
        return self._save(record)

    def complete_task(self, project_id: str, task_id: str) -> dict | None:
        record = self.get(project_id)
        if record is None:
            return None
        for task in record["tasks"]:
            if task["id"] == task_id:
                task["done"] = not task["done"]
                break
        return self._save(record)

    def delete_task(self, project_id: str, task_id: str) -> dict | None:
        record = self.get(project_id)
        if record is None:
            return None
        record["tasks"] = [t for t in record["tasks"] if t["id"] != task_id]
        return self._save(record)

    def add_note(self, project_id: str, text: str) -> dict | None:
        record = self.get(project_id)
        if record is None:
            return None
        record["notes"].append({"id": uuid.uuid4().hex[:12], "text": text, "created_at": time.time()})
        return self._save(record)

    def delete_note(self, project_id: str, note_id: str) -> dict | None:
        record = self.get(project_id)
        if record is None:
            return None
        record["notes"] = [n for n in record["notes"] if n["id"] != note_id]
        return self._save(record)

    def delete(self, project_id: str) -> dict:
        # A propósito NUNCA toca la carpeta/archivos reales de Drive — solo
        # borra el registro local de Snarf. El gate de confirmación vive en
        # el handler del Orchestrator (mismo criterio que drive_delete_file),
        # no acá adentro.
        self._path(project_id).unlink(missing_ok=True)
        return {"status": "deleted", "project_id": project_id}

    def search_within(self, project_id: str, query: str, top_k: int = 5) -> list[dict]:
        return self._indexer.search(query, top_k=top_k, where={"project_id": project_id})

    def file_count(self, project_id: str) -> int | None:
        project = self.get(project_id)
        if project is None or not project.get("drive_folder_id"):
            return None
        query = f"'{project['drive_folder_id']}' in parents and trashed = false"
        # iter_all_files pagina todo el listado — un list_files simple con
        # su default de 50 subcontaría un proyecto con más archivos que eso.
        # Las subcarpetas sugeridas (Archivos, Investigación, etc.) también
        # son "files" para la API de Drive — no cuentan como archivo real.
        return sum(
            1
            for f in self._drive.iter_all_files(query=query)
            if f.get("mimeType") != "application/vnd.google-apps.folder"
        )

    def generate_summary(self, project_id: str) -> dict | None:
        project = self.get(project_id)
        if project is None:
            return None

        llm = self._llm_factory()
        if not llm.available:
            summary_text = "No se pudo generar un resumen: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY)."
        else:
            pending = [t["text"] for t in project["tasks"] if not t["done"]]
            done = [t["text"] for t in project["tasks"] if t["done"]]
            notes = [n["text"] for n in project["notes"]]
            context_lines = [
                f"Proyecto: {project['name']}",
                f"Archivos en Drive: {self.file_count(project_id)}",
                f"Instrucciones del proyecto: {project['prompt'] or '(sin instrucciones propias todavía)'}",
                f"Tareas pendientes ({len(pending)}): " + ("; ".join(pending) or "ninguna"),
                f"Tareas completadas ({len(done)}): " + ("; ".join(done) or "ninguna"),
                f"Notas ({len(notes)}): " + ("; ".join(notes) or "ninguna"),
            ]
            try:
                summary_text = llm.generate(
                    system=self._summary_system_prompt_provider(),
                    messages=[{"role": "user", "content": "\n".join(context_lines)}],
                ).text
            except Exception as exc:
                summary_text = f"No se pudo generar el resumen: {exc}"

        project["summary"] = summary_text
        project["summary_generated_at"] = time.time()
        return self._save(project)

    def cached_summary(self, project_id: str) -> dict | None:
        project = self.get(project_id)
        if project is None:
            return None
        if not project.get("summary"):
            return self.generate_summary(project_id)
        return project
