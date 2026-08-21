import json
import time
from pathlib import Path

# Namespaced por user_id desde el día uno (mismo criterio que
# SecondBrainManager, ADR 0182/0183) — data/finance_supervisor/<user_id>/.
SUPERVISOR_DIR = Path("data/finance_supervisor")

FINANCE_SUPERVISOR_SYSTEM_PROMPT = (
    "Sos un supervisor financiero que interpreta brevemente el estado real de las finanzas del "
    "fundador, a partir ÚNICAMENTE del P&L real ya calculado que se te da — nunca inventes cifras, "
    "categorías ni tendencias que no estén en esos datos. Si los datos son insuficientes para decir "
    "algo útil, decilo explícito en vez de forzar una lectura. Escribí en español, 2 a 4 oraciones, "
    "priorizando cualquier categoría de gasto inusualmente alta o un balance neto negativo."
)


class FinanceSupervisor:
    """Especialista Cognitivo de proceso separado del loop principal (ver
    ROADMAP_SECOND_BRAIN_NOTION.md, Fase D2, ADR 0197) — interpreta
    periódicamente el estado financiero real del fundador a partir de la
    Google Sheet que ya mantiene (mismo pipeline real de
    BooksCategorizeSpecialist + MonthlyPnLSpecialist, ADR 0107 — ningún
    cálculo ni categoría nueva, solo la interpretación corta encima).
    Compone esos dos Specialists ya reales sin importar snarf.core/
    snarf.runtime (ADR 0026). Nunca ejecuta ninguna acción mutante por su
    cuenta — solo lee y guarda una interpretación."""

    def __init__(self, books_categorize, monthly_pnl, user_id: str, llm_factory=None, report_system_prompt_provider=None):
        self._books_categorize = books_categorize
        self._monthly_pnl = monthly_pnl
        self._user_id = user_id
        # llm_factory: callable sin argumentos, None si no se inyecta —
        # mismo criterio de ProjectManager/SecondBrainManager (ADR 0026).
        self._llm_factory = llm_factory
        self._report_system_prompt_provider = report_system_prompt_provider or (
            lambda: FINANCE_SUPERVISOR_SYSTEM_PROMPT
        )

    def _user_dir(self) -> Path:
        return SUPERVISOR_DIR / self._user_id

    def get_sheet_file_id(self) -> str | None:
        path = self._user_dir() / "config.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get("sheet_file_id")

    def set_sheet_file_id(self, file_id: str) -> dict:
        """Configura QUÉ Google Sheet real es "la" planilla de finanzas de
        este usuario — sin esto, refresh() no tiene de dónde leer (Snarf no
        adivina cuál de los archivos del Drive del fundador es la correcta).
        Bajo impacto: solo guarda un id local, no toca nada real de Drive."""
        path = self._user_dir() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        config = {"sheet_file_id": file_id}
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return config

    def get_snapshot(self) -> dict | None:
        path = self._user_dir() / "snapshot.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def refresh(self) -> dict | None:
        """Corre el pipeline real completo — lee la Sheet configurada,
        categoriza vía LLM, calcula el P&L determinístico, y genera una
        interpretación corta sobre esos datos reales únicamente. Devuelve
        None (nunca inventa un snapshot) si el usuario todavía no configuró
        ninguna Sheet."""
        file_id = self.get_sheet_file_id()
        if not file_id:
            return None
        categorized = self._books_categorize.categorize(file_id)
        pnl = self._monthly_pnl.compute(categorized["transactions"])

        llm = self._llm_factory() if self._llm_factory else None
        if llm is None or not llm.available:
            report_text = "No se pudo generar la interpretación: falta configurar el modelo de lenguaje."
        else:
            context = (
                f"Ingresos: {pnl['income']}. Gastos totales: {pnl['total_expenses']}. Neto: {pnl['net']}. "
                f"Gastos por categoría: {pnl['expenses_by_category']}."
            )
            try:
                report_text = llm.generate(
                    system=self._report_system_prompt_provider(),
                    messages=[{"role": "user", "content": context}],
                ).text
            except Exception as exc:
                report_text = f"No se pudo generar la interpretación: {exc}"

        snapshot = {"pnl": pnl, "report": report_text, "generated_at": time.time()}
        path = self._user_dir() / "snapshot.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot
