# ADR 0013 — Autenticación de Google y primera Capacidad de Drive

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

Primer paso de la etapa de contexto externo: darle a Snarf acceso a Google Drive (y, a futuro, Gmail/Calendar/YouTube) para que pueda ingresar, obtener y eventualmente vectorizar contenido por sí mismo, sin subida manual de archivos como prerrequisito.

## Decisión

Se creó un proyecto de Google Cloud (`snarf-503519`) con credenciales OAuth tipo "App de escritorio". Se implementó `GoogleAuth` (`snarf/capabilities/google_auth.py`), una Capacidad compartida que maneja el flujo OAuth (`google-auth-oauthlib`), cachea el token en `credentials/google_token.json` y lo refresca automáticamente. Todas las futuras Capacidades de Google (Drive, Gmail, Calendar, YouTube) reutilizan esta misma autenticación — un solo consentimiento del fundador cubre todo.

Alcance de permisos solicitado en un solo consentimiento (para no pedir autorización de nuevo por cada Capacidad futura):
- `drive.readonly` — leer Drive, sin escritura (no se pidió esa capacidad).
- `gmail.modify` + `gmail.send` — lectura y escritura de Gmail, según lo pedido explícitamente por el fundador.
- `calendar` — lectura y escritura de Calendar.
- `youtube.readonly` — preparado para una futura Capacidad de YouTube (API habilitada por el fundador, aunque no se construyó código todavía).

Se implementó `GoogleDrive` (`snarf/capabilities/google_drive.py`): `list_files` y `read_file_text` (con manejo separado para documentos nativos de Google, que requieren exportación, y archivos subidos directamente).

## Incidente durante la configuración

El primer intento de autenticación falló con "Error 403: access_denied" porque la pantalla de consentimiento de OAuth estaba en modo Prueba sin el email del fundador en la lista de usuarios de prueba. Se resolvió publicando la app (pasándola a producción, sin verificación de Google — aceptable para uso personal de un solo usuario). Documentado como precedente por si se repite al agregar Gmail/Calendar/YouTube.

## Verificado

Flujo OAuth completo ejecutado en vivo: autenticación exitosa, token guardado, y `list_files` devolvió contenido real de la cuenta de Drive del fundador (10 archivos reales, incluidas carpetas, hojas de cálculo y audio).

## Consecuencias

- `read_file_text` hoy solo maneja bien contenido de texto (Google Docs, Sheets exportados como texto/CSV, archivos de texto plano). PDFs, imágenes, audio y video en Drive todavía no se procesan — es el trabajo pendiente de "importación/extracción por tipo de archivo" ya anotado en el plan.
- `drive.readonly` es de alcance mínimo a propósito: si en el futuro se necesita que Snarf escriba en Drive, eso requiere una nueva autorización explícita (Constitution, Artículo III — competencia por delegación explícita, no asumida).
- El token vive en `credentials/`, fuera de git. Si la Mac se reinstala o el archivo se pierde, hay que rehacer el consentimiento una vez.
