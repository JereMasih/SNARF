import json
import time
from pathlib import Path

from snarf.capabilities.notion import extract_title, format_properties_text

AREA_REPORT_SYSTEM_PROMPT = (
    "Sos un asistente que escribe análisis breves, profesionales y útiles del estado actual de un "
    "Área de vida/trabajo (método PARA), a partir únicamente de los datos reales que se te dan — nunca "
    "inventes proyectos, recursos ni actividad que no esté en esa información. Si algún dato no está "
    "disponible (por ejemplo, recursos sin mapear todavía), decilo explícito en vez de omitirlo en "
    "silencio. Escribí en español, en 3 a 5 oraciones, priorizando qué proyectos están activos y qué es "
    "lo más relevante ahora mismo."
)

# Namespaced por user_id desde el día uno (data/second_brain/<user_id>/) — a
# propósito, en contraste directo con el bug real ya cometido con
# PROJECTS_DIR (snarf/specialists/project_manager.py), que quedó global y
# tuvo que namespacearse después (ver ADR 0183). Acá no hay nada viejo que
# migrar: es una carpeta nueva, así que nace bien desde el principio.
SECOND_BRAIN_DIR = Path("data/second_brain")

DATABASE_MAP_KEYS = ("areas", "proyectos", "recursos", "archivo")


def _normalize_database_map(raw: dict) -> dict:
    # Misma disciplina que ProjectManager._normalize: nunca confiar en lo
    # que hay en disco — tipos, claves faltantes.
    normalized = {key: raw.get(key) for key in DATABASE_MAP_KEYS}
    normalized["property_map"] = raw.get("property_map") if isinstance(raw.get("property_map"), dict) else {}
    return normalized


def _row_summary(row: dict) -> dict:
    properties = row.get("properties", {})
    return {
        "id": row.get("id"),
        "url": row.get("url"),
        "name": extract_title({"properties": properties}),
        "properties_text": format_properties_text(properties),
    }


class SecondBrainManager:
    """Gestiona la jerarquía Área→Proyecto→Recursos/Archivo del Second Brain
    de Notion del fundador (método PARA — ver ROADMAP_SECOND_BRAIN_NOTION.md
    y ADR 0179 para el porqué del nombre "Área", que colisiona a propósito
    con snarf/runtime/areas.py, un concepto sin relación). No es un
    Specialist de un solo handle() — mismo motivo que ProjectManager vive en
    snarf/specialists/: compone la Capacidad Notion sin importar
    snarf.core/snarf.runtime (ADR 0026).

    A diferencia de ProjectManager, esto NUNCA persiste el contenido real de
    Áreas/Proyectos/Recursos/Archivo en un JSON propio — Notion es la única
    fuente de verdad, siempre leída en vivo (ver ADR 0184: las Áreas no se
    "importan" como entidad de Snarf). Lo único que sí persiste acá es el
    MAPEO de qué database real de Notion corresponde a cada rol (el
    fundador ya tiene sus propias databases con sus propios nombres de
    propiedad — nunca se asume un esquema fijo)."""

    def __init__(self, notion, user_id: str, llm_factory=None, report_system_prompt_provider=None):
        self._notion = notion
        self._user_id = user_id
        # llm_factory: callable sin argumentos, None si no se inyecta —
        # mismo criterio de ProjectManager/GmailDigestSpecialist (ADR 0026):
        # nunca una instancia fija, para que el ruteo de LLM configurado en
        # caliente se refleje sin reiniciar el servidor. None es válido
        # (get_area_home no lo necesita, solo generate_area_report).
        self._llm_factory = llm_factory
        self._report_system_prompt_provider = report_system_prompt_provider or (lambda: AREA_REPORT_SYSTEM_PROMPT)

    def _map_path(self) -> Path:
        return SECOND_BRAIN_DIR / self._user_id / "database_map.json"

    def get_database_map(self) -> dict:
        path = self._map_path()
        if not path.exists():
            return _normalize_database_map({})
        return _normalize_database_map(json.loads(path.read_text(encoding="utf-8")))

    def save_database_map(self, database_map: dict) -> dict:
        normalized = _normalize_database_map(database_map)
        path = self._map_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        return normalized

    def is_connected(self) -> bool:
        """Second Brain "conectado" = al menos las databases de Áreas y
        Proyectos ya están mapeadas — Recursos/Archivo son opcionales
        (algunos fundadores pueden no tenerlas separadas todavía)."""
        database_map = self.get_database_map()
        return bool(database_map.get("areas")) and bool(database_map.get("proyectos"))

    def list_areas(self) -> list[dict]:
        database_id = self.get_database_map().get("areas")
        if not database_id:
            return []
        return [_row_summary(row) for row in self._notion.query_database(database_id)]

    def get_area(self, area_id: str) -> dict | None:
        try:
            page = self._notion.get_page(area_id)
        except Exception:
            return None
        if page.get("archived"):
            return None
        return _row_summary(page)

    def list_projects(self, area_id: str | None = None) -> list[dict]:
        database_map = self.get_database_map()
        database_id = database_map.get("proyectos")
        if not database_id:
            return []
        filter_ = None
        if area_id:
            filter_ = {
                "property": self._relation_property(database_map, "proyecto_area_relation", "Proyectos", "Área"),
                "relation": {"contains": area_id},
            }
        return [_row_summary(row) for row in self._notion.query_database(database_id, filter=filter_)]

    def get_project(self, project_id: str) -> dict | None:
        try:
            page = self._notion.get_page(project_id)
        except Exception:
            return None
        if page.get("archived"):
            return None
        return _row_summary(page)

    def list_resources(self, project_id: str) -> list[dict]:
        return self._list_related_to_project(project_id, "recursos", "recurso_proyecto_relation", "Recursos")

    def list_archive(self, project_id: str) -> list[dict]:
        return self._list_related_to_project(project_id, "archivo", "archivo_proyecto_relation", "Archivo")

    def _list_related_to_project(
        self, project_id: str, database_key: str, relation_key: str, database_label: str
    ) -> list[dict]:
        database_map = self.get_database_map()
        database_id = database_map.get(database_key)
        if not database_id:
            return []
        filter_ = {
            "property": self._relation_property(database_map, relation_key, database_label, "Proyecto"),
            "relation": {"contains": project_id},
        }
        return [_row_summary(row) for row in self._notion.query_database(database_id, filter=filter_)]

    def get_area_home(self, area_id: str) -> dict | None:
        """Panorama agregado real de un Área: sus Proyectos, más Recursos y
        Archivo de TODOS esos Proyectos juntos (no solo listar Proyectos).
        `resources_mapped`/`archive_mapped` distinguen "cero real" de "no se
        puede saber, falta mapear la property de relación" — nunca se
        muestra un cero como si fuera un dato real cuando en realidad es
        desconocido (Principio VI, Foundation)."""
        area = self.get_area(area_id)
        if area is None:
            return None
        projects = self.list_projects(area_id=area_id)
        database_map = self.get_database_map()
        property_map = database_map.get("property_map", {})
        resources_mapped = bool(database_map.get("recursos")) and bool(property_map.get("recurso_proyecto_relation"))
        archive_mapped = bool(database_map.get("archivo")) and bool(property_map.get("archivo_proyecto_relation"))

        resources: list[dict] = []
        archive: list[dict] = []
        if resources_mapped:
            for project in projects:
                resources.extend(self.list_resources(project["id"]))
        if archive_mapped:
            for project in projects:
                archive.extend(self.list_archive(project["id"]))

        return {
            "area": area,
            "projects": projects,
            "resources": resources,
            "resources_mapped": resources_mapped,
            "archive": archive,
            "archive_mapped": archive_mapped,
        }

    def _area_report_path(self, area_id: str) -> Path:
        return SECOND_BRAIN_DIR / self._user_id / "area_reports" / f"{area_id}.json"

    def _read_area_report(self, area_id: str) -> dict | None:
        path = self._area_report_path(area_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_area_report(self, area_id: str, report_text: str) -> dict:
        record = {"report": report_text, "report_generated_at": time.time()}
        path = self._area_report_path(area_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def generate_area_report(self, area_id: str) -> dict | None:
        home = self.get_area_home(area_id)
        if home is None:
            return None

        llm = self._llm_factory() if self._llm_factory else None
        if llm is None or not llm.available:
            report_text = "No se pudo generar el reporte: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY)."
        else:
            project_names = [p["name"] for p in home["projects"]]
            context_lines = [
                f"Área: {home['area']['name']}",
                f"Proyectos ({len(project_names)}): " + ("; ".join(project_names) or "ninguno"),
                (
                    f"Recursos totales: {len(home['resources'])}"
                    if home["resources_mapped"]
                    else "Recursos: sin mapear todavía en el Second Brain (no se puede saber cuántos hay)"
                ),
                (
                    f"Archivados totales: {len(home['archive'])}"
                    if home["archive_mapped"]
                    else "Archivo: sin mapear todavía en el Second Brain (no se puede saber cuántos hay)"
                ),
            ]
            try:
                report_text = llm.generate(
                    system=self._report_system_prompt_provider(),
                    messages=[{"role": "user", "content": "\n".join(context_lines)}],
                ).text
            except Exception as exc:
                report_text = f"No se pudo generar el reporte: {exc}"

        saved = self._save_area_report(area_id, report_text)
        return {**home, **saved}

    def cached_area_report(self, area_id: str) -> dict | None:
        home = self.get_area_home(area_id)
        if home is None:
            return None
        cached = self._read_area_report(area_id)
        if cached is None:
            return self.generate_area_report(area_id)
        return {**home, **cached}

    def auto_build_workspace(self, parent_page_id: str) -> dict:
        """Crea la estructura completa del Second Brain desde cero, bajo una
        página real que el fundador ya compartió con la integración
        (`parent_page_id` — Notion no permite crear una página en la raíz
        del workspace, solo como hija de algo ya accesible): una página raíz
        "Snarf Second Brain" + 4 databases (Área/Proyecto/Recursos/Archivo,
        método PARA) con relaciones reales entre ellas, y completa
        `database_map.json` con los ids reales creados y el `property_map`
        de las relaciones (ver ADR 0190). Alto impacto — quien llama (el
        handler del Orchestrator) exige `confirmed=true` antes de invocar
        esto, no hay gate acá adentro."""
        root = self._notion.create_page(
            parent_page_id,
            "Snarf Second Brain",
            "Esta página y las databases de acá abajo son tu Second Brain real, gestionado por Snarf "
            "(método PARA: Área, Proyecto, Recursos, Archivo). Podés verlas y editarlas acá en Notion "
            "en cualquier momento — Snarf las refleja en vivo, nunca duplica el contenido.",
        )
        root_id = root["id"]

        areas_db = self._notion.create_database(root_id, "Áreas", {"Nombre": {"title": {}}})
        proyectos_db = self._notion.create_database(
            root_id,
            "Proyectos",
            {
                "Nombre": {"title": {}},
                "Área": {"relation": {"database_id": areas_db["id"], "single_property": {}}},
            },
        )
        recursos_db = self._notion.create_database(
            root_id,
            "Recursos",
            {
                "Nombre": {"title": {}},
                "Proyecto": {"relation": {"database_id": proyectos_db["id"], "single_property": {}}},
            },
        )
        archivo_db = self._notion.create_database(
            root_id,
            "Archivo",
            {
                "Nombre": {"title": {}},
                "Proyecto": {"relation": {"database_id": proyectos_db["id"], "single_property": {}}},
            },
        )

        database_map = self.save_database_map(
            {
                "areas": areas_db["id"],
                "proyectos": proyectos_db["id"],
                "recursos": recursos_db["id"],
                "archivo": archivo_db["id"],
                "property_map": {
                    "proyecto_area_relation": "Área",
                    "recurso_proyecto_relation": "Proyecto",
                    "archivo_proyecto_relation": "Proyecto",
                },
            }
        )
        return {"root_page_id": root_id, "root_page_url": root.get("url"), "database_map": database_map}

    def suggest_mapping(self) -> dict:
        """Busca databases YA existentes en el workspace del fundador cuyo
        nombre se parezca a Área/Proyecto/Recursos/Archivo (coincidencia
        real de palabras clave, no una llamada a un LLM — mantiene esto
        barato y determinístico) y propone un mapeo. Nunca lo guarda por su
        cuenta: quien llama debe confirmarlo explícito con
        save_database_map() antes de que tenga efecto real (ver ADR 0190)."""
        all_databases = list(self._notion.iter_all_databases())
        keywords = {
            "areas": ("área", "areas", "life areas"),
            "proyectos": ("proyecto", "projects"),
            "recursos": ("recurso", "resources"),
            "archivo": ("archivo", "archive"),
        }
        suggestions = {}
        for role, terms in keywords.items():
            match = next(
                (db for db in all_databases if any(term in db["title"].lower() for term in terms)),
                None,
            )
            if match:
                suggestions[role] = {"id": match["id"], "title": match["title"], "url": match["url"]}
        return {"suggestions": suggestions, "all_databases": all_databases}

    def create_project_row(self, name: str) -> str | None:
        """Crea una fila nueva en la database de Proyectos real del
        fundador, para un Proyecto que nace desde Snarf (ver ADR 0184,
        usado por ProjectManager.create()). Devuelve None (nunca levanta)
        si el Second Brain no está conectado o si la database no tiene una
        property de título reconocible — un Proyecto de Snarf siempre puede
        crearse igual, con o sin Notion; el vínculo es un extra, no un
        prerrequisito."""
        if not self.is_connected():
            return None
        database_id = self.get_database_map().get("proyectos")
        if not database_id:
            return None
        try:
            schema = self._notion.get_database(database_id)
            title_property = next(
                (prop_name for prop_name, prop_type in schema["properties"].items() if prop_type == "title"),
                None,
            )
            if not title_property:
                return None
            result = self._notion.create_database_item(
                database_id, {title_property: {"title": [{"text": {"content": name}}]}}
            )
            return result.get("id")
        except Exception:
            return None

    @staticmethod
    def _relation_property(database_map: dict, relation_key: str, database_label: str, target_label: str) -> str:
        # Nunca filtrar a ciegas: sin saber el nombre real de la property de
        # relación en la database del fundador, un filtro inventado
        # devolvería un resultado vacío o incorrecto sin ningún aviso —
        # mejor fallar explícito (Principio VI, Foundation) y que quien
        # llama complete property_map primero (ver A4, onboarding).
        relation_property = database_map.get("property_map", {}).get(relation_key)
        if not relation_property:
            raise ValueError(
                f"No hay mapeo de la property que relaciona {database_label} con {target_label} "
                f"(property_map.{relation_key}) — completar el database_map del Second Brain antes "
                f"de filtrar por {target_label}."
            )
        return relation_property
