from snarf.specialists.base import Specialist

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "category": {"type": "string"},
                },
            },
        }
    },
    "required": ["transactions"],
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "income": {"type": "number"},
        "expenses_by_category": {"type": "object"},
        "total_expenses": {"type": "number"},
        "net": {"type": "number"},
    },
}


class MonthlyPnLSpecialist(Specialist):
    """P&L real y determinístico sobre transacciones YA categorizadas (ver
    BooksCategorizeSpecialist) — nunca un LLM: sumar montos reales no
    necesita interpretación, y un cálculo determinístico es más confiable
    que uno generado."""

    name = "monthly_pnl"
    domain = "finance"

    def compute(self, transactions: list[dict]) -> dict:
        income = 0.0
        expenses_by_category: dict[str, float] = {}
        for t in transactions:
            amount = t.get("amount", 0.0)
            if amount >= 0:
                income += amount
            else:
                category = t.get("category") or "sin categorizar"
                expenses_by_category[category] = expenses_by_category.get(category, 0.0) + amount
        total_expenses = sum(expenses_by_category.values())
        return {
            "income": round(income, 2),
            "expenses_by_category": {k: round(v, 2) for k, v in expenses_by_category.items()},
            "total_expenses": round(total_expenses, 2),
            "net": round(income + total_expenses, 2),
        }

    def handle(self, task: str, context: dict) -> str:
        pnl = self.compute(context.get("transactions", []))
        return f"Ingresos: {pnl['income']} | Gastos: {pnl['total_expenses']} | Neto: {pnl['net']}"
