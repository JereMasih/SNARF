# ADR 0107 — Fase I: rama Finance (v1 — libro mayor + P&L reales)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Sexta rama de la Fase I. El plan nombraba 6 piezas (`BooksCategorizeSpecialist`,
`MonthlyPnLSpecialist`, `TaxPrepSpecialist`, `AnomalyScanSpecialist`, `SubsAuditSpecialist`,
`ReceiptsTrackerSpecialist`) sobre una arquitectura de datos ya decidida: v1 sin vendor nuevo, una
Google Sheet real que el fundador mantiene, Plaid como upgrade real posterior — nunca como bloqueo
de v1.

## Decisión

**Confirmado sin código nuevo**: `GoogleDrive.read_file_text(file_id,
"application/vnd.google-apps.spreadsheet")` YA exporta un Google Sheet real como CSV
(`GOOGLE_DOCS_EXPORT_MIME`, ver `google_drive.py`) — la premisa del plan ("reusa GoogleDrive/Sheets,
sin OAuth nuevo") se verificó real, no asumida, antes de escribir código nuevo.

1. **`snarf/specialists/finance/transactions.py::parse_transactions_csv`**: parseo real y tolerante
   (columnas en español o inglés, monta con separador de miles/símbolo de moneda) — una fila real
   pero rota se salta, nunca rompe el resto; sin columnas reconocibles, devuelve lista vacía, nunca
   inventa una transacción.
2. **`BooksCategorizeSpecialist`**: lee la Sheet real, categoriza cada transacción real vía LLM
   (formato de respuesta fijo `<índice>: <categoría>`, parseado con tolerancia — un índice sin
   respuesta cae a `"sin categorizar"`, nunca inventa una categoría fantasma).
3. **`MonthlyPnLSpecialist`**: determinístico, sin LLM — suma real de ingresos/gastos por categoría
   sobre transacciones ya categorizadas. Sumar montos reales no necesita interpretación; un cálculo
   determinístico es más confiable que uno generado.

## Explícitamente diferido en esta ronda (no silenciado — nombrado y con motivo concreto)

- **`TaxPrepSpecialist`**: necesita la estructura real de Schedule C (categorías fiscales reales de
  EE.UU., no inventadas) — investigación real pendiente antes de poder construirse honesto.
- **`AnomalyScanSpecialist`** / **`SubsAuditSpecialist`**: ambos necesitan volumen real de
  transacciones categorizadas para calibrar qué es "outlier"/"cargo recurrente" de verdad — sin
  datos reales del fundador todavía (la Sheet real recién se conecta), calibrar esto ahora sería
  adivinar el umbral, no construir sobre datos reales.
- **`ReceiptsTrackerSpecialist`**: la extracción por visión que reutilizaría ya existe
  (`ContentExtractor`/`drive_vision`, ADR 0028) — falta solo el flujo de asociar un recibo subido a
  una transacción real de la Sheet; se construye en cuanto haya transacciones reales categorizadas
  con las que asociarlo.

Ninguno de los cuatro está bloqueado por falta de vendor o credencial — quedan nombrados como
siguiente trabajo real y concreto sobre la base ya construida, no como "no lo tenemos, lo dejamos
para después" sin fecha.

## Verificado

- 16 tests nuevos: `tests/test_finance_transactions.py` (7), `tests/test_books_categorize.py` (5),
  `tests/test_monthly_pnl.py` (4).
- 890/890 tests de la suite completa.

## Consecuencias

- En cuanto el fundador comparta el `file_id` real de su Sheet de transacciones, la rama queda
  operativa de punta a punta sin ningún cambio de código.
