import json
import time
from pathlib import Path

# Namespaced por user_id desde el día uno (mismo criterio que
# FinanceSupervisor/SecondBrainManager) — data/founder_mood/<user_id>/.
MOOD_DIR = Path("data/founder_mood")

FOUNDER_MOOD_SYSTEM_PROMPT = (
    "Sos un supervisor que interpreta señales reales de ánimo/estado del fundador a partir "
    "ÚNICAMENTE de los últimos mensajes reales que escribió — nunca inventes un estado de ánimo sin "
    "evidencia textual concreta. Cada afirmación lleva una etiqueta de base real: 'hecho' (solo si hay "
    "una frase textual citable que lo sostenga directamente), 'inferencia' (una lectura razonable a "
    "partir de lo escrito, pero no dicha explícitamente), o 'hipótesis' (una posibilidad, sin "
    "evidencia fuerte). Si no hay señales reales claras, decilo explícito ('sin señales claras en los "
    "últimos mensajes') en vez de forzar una lectura — inventar un estado de ánimo sin evidencia es "
    "peor que no decir nada. Formato: una línea por señal real encontrada, "
    "'<basis>: <observación breve, citando o parafraseando lo real>'. Español, máximo 4 líneas."
)


class FounderMood:
    """Especialista Cognitivo de proceso separado (ancla en el slot
    FOUNDER_MODEL activado en COGNITION.md, ADR 0179) — interpreta señales
    reales de ánimo/estado del fundador desde la ÚNICA fuente honesta
    disponible: la memoria episódica reciente. Misma disciplina de basis/
    honestidad que la Inteligencia Ejecutiva (ADR 0094) — más importante
    acá que en cualquier otro Especialista, porque es fácil que un LLM
    "invente" un estado de ánimo sin evidencia real (Principio VI,
    Foundation). Nunca ejecuta ninguna acción mutante — solo lee memoria y
    guarda una interpretación."""

    def __init__(self, memory, user_id: str, llm_factory=None, report_system_prompt_provider=None):
        self._memory = memory
        self._user_id = user_id
        self._llm_factory = llm_factory
        self._report_system_prompt_provider = report_system_prompt_provider or (lambda: FOUNDER_MOOD_SYSTEM_PROMPT)

    def _snapshot_path(self) -> Path:
        return MOOD_DIR / self._user_id / "snapshot.json"

    def get_snapshot(self) -> dict | None:
        path = self._snapshot_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def refresh(self, recent_n: int = 10) -> dict:
        recent = self._memory.recent(recent_n)
        real_inputs = [entry["input"] for entry in recent if entry.get("input")]

        if not real_inputs:
            report_text = "sin señales claras en los últimos mensajes (todavía no hay conversación real)"
        else:
            llm = self._llm_factory() if self._llm_factory else None
            if llm is None or not llm.available:
                report_text = "No se pudo generar la interpretación: falta configurar el modelo de lenguaje."
            else:
                context = "\n".join(f"- {text}" for text in real_inputs)
                try:
                    report_text = llm.generate(
                        system=self._report_system_prompt_provider(),
                        messages=[{"role": "user", "content": context}],
                    ).text
                except Exception as exc:
                    report_text = f"No se pudo generar la interpretación: {exc}"

        snapshot = {"report": report_text, "generated_at": time.time()}
        path = self._snapshot_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot
