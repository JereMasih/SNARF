# ADR 0024 — Fixes de layout Jarvis, CI y arrastre; widgets más útiles

**Fecha:** 2026-07-27
**Estado:** Aceptado — verificado con navegador real (Playwright) por primera vez en este proyecto

## Contexto

El fundador probó ADR 0023 en su Mac y su celular reales y reportó, con capturas de pantalla: el layout Jarvis de desktop se veía completamente roto (sin paneles visibles, solo el orbe y fragmentos sueltos); el arrastre para reordenar no funcionaba en el celular; los widgets de Drive/Gmail/YouTube mostraban listas sin contexto, no cliqueables, con poca información; y de paso encontró, mirando el widget de Gmail, que el último push a `master` había roto el CI en GitHub Actions.

Hasta esta ronda, la verificación de interfaz dependía de leer el código y pedir capturas del fundador — sin navegador disponible en este entorno de desarrollo. Se instaló `playwright` (Chromium headless) en el entorno virtual del proyecto, lo que permitió, por primera vez, reproducir el bug exacto del fundador, inspeccionar estilos computados y `elementFromPoint` para encontrar la causa real, y confirmar cada fix con una captura de pantalla propia antes de devolvérselo. `playwright` no se agregó a `requirements-dev.txt` — es una herramienta de verificación de esta sesión, no una dependencia del proyecto ni de su suite de tests automatizada.

## Decisión

1. **Bug real del layout Jarvis, encontrado con `document.elementFromPoint`:** `#appRoot` no tenía `position`/`z-index` propios. Los fondos fijos (`.bg-glow`, `.nebula`, `.grid`; `position: fixed`, `z-index: 0`) pintan por encima de cualquier contenido no posicionado del documento, sin importar su orden en el HTML — por eso `.chat`/`.control-bar`/`.dash-mobile-stack` (que si tenían `position: relative; z-index: 2`) siempre se vieron bien, y las tres zonas nuevas del layout Jarvis (arriba/izquierda/derecha), que no tenían esa declaración, quedaban geométricamente bien ubicadas (confirmado con `getBoundingClientRect`) pero visualmente tapadas por el fondo. Fix de una línea: `#appRoot { position: relative; z-index: 2; }`. Confirmado con captura de pantalla real: el layout completo aparece correctamente.

2. **CI roto, encontrado con `gh run view --log-failed`:** `ModuleNotFoundError: No module named 'snarf'` / `'app'`. Causa real: el workflow corre `pytest` a secas, no `python -m pytest`; solo `python -m X` agrega el directorio actual a `sys.path`, así que `pytest` no encontraba ni `app.py` ni `snarf/` en el runner de GitHub. Localmente nunca se notó porque siempre se corrió con `python -m pytest`. Reproducido en la Mac con `.venv/bin/pytest` (falla igual) y corregido agregando `pythonpath = .` a `pytest.ini` — opción nativa de pytest≥7, sin plugins nuevos.

3. **Arrastre roto en celular real, no reproducible con un toque sintético "perfecto":** el código cancelaba el modo arrastre si el dedo se movía más de 6px durante los 350ms de espera — un umbral irreal para un dedo humano, que tiembla más que eso incluso "quieto". Se reprodujo con Playwright disparando `PointerEvent`s con jitter realista (±6-9px) durante la espera, confirmando que el arrastre se cancelaba. Se eliminó esa cancelación por completo: como el asa ya tiene `touch-action: none`, el navegador nunca le iba a robar el gesto para hacer scroll, así que cancelar por jitter no protegía nada real, solo rompía el caso de uso normal. Se agrandó además el área táctil del asa (mínimo 32×32px) — 14px con poco padding es menor al mínimo recomendado para un dedo real.

4. **Widgets con más contexto y cliqueables**, con datos que ya se pedían a las APIs de Google pero no se exponían:
   - Cada widget ahora tiene un subtítulo corto explicando qué muestra (ninguno se entendía por sí solo, según el fundador).
   - `GoogleDrive.list_files` ahora también pide `webViewLink`; el widget muestra fecha y tamaño de cada archivo y lo linkea a Drive.
   - `GoogleCalendar.list_upcoming_events` ahora también expone `htmlLink`; los eventos son cliqueables.
   - `GoogleYouTube.list_subscriptions` ahora también expone `channel_id`; los canales enlazan a su página real de YouTube.
   - Gmail: cada mensaje enlaza a `https://mail.google.com/mail/u/0/#all/<id>`.
   - **Corrección de seguridad, otra vez:** los nuevos campos (links, tamaños) que vienen de fuentes externas se escapan igual que el resto (`escapeHtml`), coherente con el fix de ADR 0023.
   - Nueva opción **dentro del propio widget** de Gmail (pedida explícitamente así, no escondida en configuración): un selector de 5/10/20 mensajes a mostrar, persistido por usuario (`widget_options.gmail.max_results` en `dashboard_prefs`). El endpoint `GET /dashboard/widgets/gmail` acepta `?max_results=` (clamp 1-20).

## Descartado explícitamente en esta ronda

- La idea de una Capacidad/Especialista que interprete el correo (categorizar, resumir, decidir qué es importante y por qué, invocable y con refresco periódico): el propio fundador la planteó sin tenerla definida todavía. Se propone por separado, sin construir nada hasta acordar el alcance — ver conversación; queda pendiente de una próxima ronda con alcance explícito, para no repetir el error de ADR 0022 de construir sobre una idea todavía sin forma.

## Verificado

- Suite completa: 73/73 (5 tests nuevos: normalización de `widget_options.gmail.max_results`, y que el endpoint de Gmail respeta y clampea `max_results`), corrida con `pytest` a secas (igual que CI) además de `python -m pytest`.
- **Primera vez en el proyecto verificando con un navegador real** (Playwright + Chromium headless): capturas de pantalla de desktop y mobile después de cada fix, inspección de estilos computados, y una simulación de arrastre táctil con jitter realista vía `PointerEvent`s reales — no solo lectura de código.
- Enlaces de los widgets verificados contra la cuenta real del fundador: Drive (Google Docs/Sheets/Maps/carpeta/archivo, según corresponda), Gmail, YouTube — todas las URLs resueltas son las reales de Google, no inventadas.
- Se encontró y limpió, dos veces, contaminación real de `data/dashboard_prefs/fundador.json` generada por mis propias pruebas contra el servidor aislado (puerto 8001, que por defecto lee/escribe el `data/` real si no se lo redirige) — corregido además el test `test_dashboard_preferences_defaults_before_any_save`, que no aislaba `PREFS_DIR` y por eso podía fallar según el estado real del directorio.

## Consecuencias

- Playwright queda disponible en el entorno virtual local para verificación visual futura en esta máquina — no es una dependencia del proyecto ni corre en CI, así que no se agregó a `requirements-dev.txt`.
- Cualquier prueba manual futura contra una instancia de `app.py` corriendo con el `data/` real del proyecto (en vez de un `tmp_path` aislado) puede escribir preferencias de dashboard reales por accidente — vale la pena, de acá en más, redirigir `dashboard_prefs.PREFS_DIR` explícitamente en cualquier verificación manual, igual que ya se hace con la memoria episódica.
