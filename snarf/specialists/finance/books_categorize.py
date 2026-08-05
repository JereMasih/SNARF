import re

from snarf.specialists.base import Specialist
from snarf.specialists.finance.transactions import Transaction, parse_transactions_csv

SYSTEM_PROMPT = (
    "Categorizás transacciones financieras reales del fundador de Snarf. Dado un listado numerado "
    "de transacciones reales (fecha, descripción, monto — monto negativo es un gasto, positivo un "
    "ingreso), asignale a cada una una categoría real y concreta (ej. 'software', 'oficina', "
    "'ingresos por servicios', 'impuestos', 'viajes', 'marketing', la que mejor describa cada una — "
    "vos elegís el nombre, no hay una lista fija). Respondé en español, EXACTAMENTE en este "
    "formato, una línea por transacción, en el mismo orden:\n\n"
    "<número>: <categoría>\n\n"
    "Nunca te saltees una transacción, nunca agregues texto alrededor."
)

INPUT_SCHEMA = {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"transaction_count": {"type": "integer"}, "transactions": {"type": "array"}},
}

_LINE_RE = re.compile(r"^(\d+):\s*(.+)$")


def _parse_categories(text: str, count: int) -> dict[int, str]:
    categories: dict[int, str] = {}
    for line in text.splitlines():
        match = _LINE_RE.match(line.strip())
        if not match:
            continue
        index = int(match.group(1))
        if 1 <= index <= count:
            categories[index] = match.group(2).strip()
    return categories


class BooksCategorizeSpecialist(Specialist):
    """Lee una Google Sheet real de transacciones (v1: la que el fundador
    mantiene o exporta de su banco/contable — ver ADR de esta ronda, cero
    vendor nuevo) y categoriza cada transacción real vía LLM."""

    name = "books_categorize"
    domain = "finance"

    def __init__(self, drive, llm_factory, user_id: str):
        self._drive = drive
        self._llm_factory = llm_factory
        self._user_id = user_id

    def categorize(self, file_id: str) -> dict:
        csv_text = self._drive.read_file_text(file_id, "application/vnd.google-apps.spreadsheet")
        transactions = parse_transactions_csv(csv_text)
        if not transactions:
            return {"transaction_count": 0, "transactions": [], "note": "Sin transacciones reales que categorizar."}

        llm = self._llm_factory()
        if not llm.available:
            return {
                "transaction_count": len(transactions),
                "transactions": [self._to_dict(t) for t in transactions],
                "note": "No se pudo categorizar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY).",
            }

        listing = "\n".join(f"{i}. {t.date} | {t.description} | {t.amount}" for i, t in enumerate(transactions, 1))
        response = llm.generate(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": listing}])
        categories = _parse_categories(response.text, len(transactions))

        categorized = [
            Transaction(t.date, t.description, t.amount, category=categories.get(i, "sin categorizar"))
            for i, t in enumerate(transactions, 1)
        ]
        return {"transaction_count": len(categorized), "transactions": [self._to_dict(t) for t in categorized]}

    @staticmethod
    def _to_dict(t: Transaction) -> dict:
        return {"date": t.date, "description": t.description, "amount": t.amount, "category": t.category}

    def handle(self, task: str, context: dict) -> str:
        result = self.categorize(context.get("file_id", ""))
        return result.get("note") or f"{result['transaction_count']} transacciones categorizadas."
