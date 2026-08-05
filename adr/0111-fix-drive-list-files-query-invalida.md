# ADR 0111 — Fix real: `drive_list_files` fallaba con texto libre como query

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Revisando `data/activity_log.jsonl` a pedido del fundador ("revisa las últimas llamadas a Snarf y
corrige errores") se encontró un patrón real y recurrente: `drive_list_files` fallando con
`HttpError 400 ... "Invalid Value"` cada vez que la query pasada era texto libre (`Peso_16-07-2026`,
`Tommy`, `vida es sueño`) en vez de la sintaxis real que exige la API de Google Drive
(`fullText contains 'vida es sueño'`). El caso más reciente: el fundador buscó contenido real sobre
"La vida es sueño" y Snarf reintentó 3 veces con variantes de texto libre, las 3 fallaron con el
mismo 400 real, antes de recién ahí (no queda registrado con qué query exacta) conseguir un resultado.

## Decisión

`snarf/capabilities/google_drive.py::normalize_drive_query()` (nuevo): si la query ya parece
sintaxis real de Drive (contiene un operador reconocible — `contains`, `in`, `=`, `<`, `>`, todos
verificados con `\b` para nunca confundir un operador real con una substring dentro de otra palabra,
ej. "in" dentro de "Argentina"), se pasa intacta. Si no, se envuelve automáticamente como
`fullText contains '<texto escapado>'` — el caso real y más común de lejos. Aplicado en el único
lugar real donde `query` se convierte en el parámetro `q` de la API (`list_files`/`list_files_page`),
así que cubre automáticamente a todos los callers reales (`drive_list_files`,
`drive_index_scan`/`drive_index_start`/`drive_index_catalog_unsupported` vía `iter_all_files`) sin
tocarlos uno por uno. `get_or_create_folder()` (que sí construye sintaxis real internamente, con `=`
e `in`) sigue funcionando exactamente igual — verificado que su query pasa el detector sin cambios.

Descripción del tool `drive_list_files` actualizada para reflejar el comportamiento real nuevo
(acepta texto libre, no solo sintaxis de Drive).

## Verificado

- 11 tests nuevos: `tests/test_drive_query_normalization.py` (9, incluye escape de comillas simples,
  no-falso-positivo de `in` dentro de otra palabra, texto con comillas dobles/`OR` mal formado
  tratado como un solo literal), 2 en `tests/test_google_drive.py` (wiring real de `list_files`).
- **Verificado contra Drive real, no solo mocks**: la query exacta que fallaba en producción
  (`vida es sueño`) corrida en vivo después del fix — sin 400, 5 resultados reales, incluidos los
  documentos reales que el fundador buscaba ("La vida es sueño - Versión para lectura en voz",
  "Análisis completo de 'La vida es sueño'", etc.).
- 928/928 tests de la suite completa.

## Consecuencias

- Requiere reiniciar el server real de producción para que la corrección entre en vigencia en
  llamadas reales — confirmar con el fundador antes (mismo criterio de CLAUDE.md).
