# ADR 0114 — Fix real: dos bugs de indexado de Drive (no el pipeline completo)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

El fundador reportó que el indexado de Google Drive "se perdió" en algún punto entre iteraciones y
pidió llegar al fondo. Investigando el código, `data/drive_index/fundador/` y `usage_log.jsonl`
reales se encontró que **el pipeline no estaba roto**: `chromadb.sqlite3` (386MB) tenía timestamp de
la misma madrugada de esta sesión, el manifiesto mostraba 4658 archivos `indexed`, `VOYAGE_API_KEY`
seguía funcionando (87 llamadas reales registradas), y los 36 tests de `knowledge` pasaban. Lo que sí
se encontraron fueron dos bugs concretos que explican por qué *parecía* roto:

1. `DriveIndexer._status` es estado en memoria de proceso, reseteado a idle en cada
   `__init__()`/`start()`. La tool de chat `drive_index_status` reportaba ese dict efímero en vez del
   progreso real persistido (`manifest_summary()`, que sí usa el dashboard/cerebro) — cada reinicio
   del server durante desarrollo activo hacía que el chat dijera "0 indexados" pese a que el índice en
   disco seguía intacto y avanzando.
2. `VectorStore.add()` le pasaba a `chromadb.Collection.add()` la lista completa de embeddings de un
   archivo de una sola vez, sin trocear al límite real de batch de chromadb (~5461 en esta
   instalación) — un archivo con muchos chunks (ej. una transcripción de video larga) fallaba siempre
   con `ValueError: Batch size of N is greater than max batch size`.

## Decisión

- `DriveIndexer.status()`: cuando `running` es `False`, combina el dict efímero con
  `manifest_summary()` para `indexed`/`errors` — el chat ahora refleja el progreso real persistido
  incluso después de un reinicio del server. Mientras SÍ está corriendo, el contador en memoria de esa
  corrida se deja tal cual.
- `VectorStore.add()`: trocea en lotes de `_ADD_BATCH_SIZE = 1000` (mismo tamaño que
  `VoyageEmbeddings.embed()` ya usa para su propia API) antes de pasarlos a chromadb.

## Verificado

- `tests/test_drive_indexer.py::test_status_reflects_persisted_progress_after_a_restart` — instancia
  nueva de `DriveIndexer` sobre un manifiesto con progreso ya persistido, simulando un reinicio real.
- `tests/test_vector_store.py::test_add_batches_large_inserts_to_stay_under_chromas_limit` — fuerza
  un batch chico para probar el troceo sin insertar miles de vectores reales.
- 946/946 tests de la suite completa.

## Consecuencias

- Ninguna migración de datos necesaria — el manifiesto y el índice existentes ya eran válidos, esto
  corrige solo cómo se reporta/inserta, no reconstruye nada desde cero.
- Requiere reiniciar el server real de producción para que el fix entre en vigencia — hecho en esta
  misma sesión.
