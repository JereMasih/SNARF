"""Parseo real de transacciones (Fase I, rama Finance — ver plan de
expansión "Inteligencia Ejecutiva"). v1 sin vendor nuevo: una Google Sheet
real que el fundador mantiene (o exporta de su banco/contable actual), leída
vía `GoogleDrive.read_file_text()` (ya exporta un Sheet real como CSV, sin
capacidad nueva — ver GOOGLE_DOCS_EXPORT_MIME en google_drive.py). Nombres
de columna flexibles (español/inglés) — nunca inventa una transacción que no
esté en el CSV real."""

import csv
import io
from dataclasses import dataclass

_DATE_KEYS = {"date", "fecha"}
_DESCRIPTION_KEYS = {"description", "descripcion", "descripción", "concepto", "detalle"}
_AMOUNT_KEYS = {"amount", "monto", "importe"}


@dataclass(frozen=True)
class Transaction:
    date: str
    description: str
    amount: float
    category: str | None = None


def _normalize_header(header: str) -> str:
    return header.strip().lower()


def _find_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    for name in fieldnames:
        if _normalize_header(name) in candidates:
            return name
    return None


def parse_transactions_csv(csv_text: str) -> list[Transaction]:
    """Nunca revienta con un CSV real pero imperfecto: una fila sin fecha/
    descripción/monto real y parseable se salta, no rompe el resto. Un CSV
    vacío o sin las columnas esperadas devuelve lista vacía — nunca inventa
    una transacción para "completar" algo."""
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    date_col = _find_column(fieldnames, _DATE_KEYS)
    desc_col = _find_column(fieldnames, _DESCRIPTION_KEYS)
    amount_col = _find_column(fieldnames, _AMOUNT_KEYS)
    if not (date_col and desc_col and amount_col):
        return []

    transactions = []
    for row in reader:
        raw_amount = (row.get(amount_col) or "").replace(",", "").replace("$", "").strip()
        try:
            amount = float(raw_amount)
        except ValueError:
            continue
        date = (row.get(date_col) or "").strip()
        description = (row.get(desc_col) or "").strip()
        if not date or not description:
            continue
        transactions.append(Transaction(date=date, description=description, amount=amount))
    return transactions
