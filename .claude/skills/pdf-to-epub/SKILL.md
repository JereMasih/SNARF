---
name: pdf-to-epub
description: Convierte PDFs, TXT o Markdown en archivos EPUB3 válidos, listos para lectores de ebooks (Kindle vía conversión, Apple Books, Google Play Books, etc.). Detecta automáticamente si el documento es un guion teatral/de cine (diálogos "Nombre.- texto" con escenas/actos), un texto en capítulos (encabezados Markdown, "Capítulo N", números romanos), o un texto corrido sin estructura, y genera la navegación, tabla de contenidos, portada y CSS apropiados para cada caso. Usar esta skill SIEMPRE que el usuario pida convertir un documento a epub o ebook, "hacer un libro digital", "pasar esto a formato para Kindle/lector", o suba un PDF/manuscrito/guion y pida un archivo descargable para leer en un ereader — incluso si no menciona la palabra "epub" explícitamente. También usar cuando otro agente o skill necesite producir un ebook como parte de un flujo mayor (por ejemplo, generación de contenido, publicación, o pipelines de documentos).
license: Uso interno del usuario — no redistribuir.
---

# pdf-to-epub

Convierte un documento fuente (PDF, TXT o Markdown) en un archivo `.epub` válido (EPUB3, con `toc.ncx` para compatibilidad EPUB2), usando un único script que hace todo el trabajo: extracción de texto, detección de estructura, generación de XHTML semántico y empaquetado del zip con la estructura correcta (`mimetype` sin comprimir y primero en el archivo, `META-INF/container.xml`, `OEBPS/content.opf`, `nav.xhtml`, `toc.ncx`, hojas de estilo).

## Cuándo usarla

- El usuario sube un PDF (guion, libro, manuscrito, informe, ensayo) y pide convertirlo a epub / ebook / "formato para Kindle o lector".
- El usuario tiene un `.txt` o `.md` y quiere un ebook navegable.
- Otro agente o skill necesita producir un `.epub` como parte de una tarea más grande (por ejemplo, un agente de publicación de contenidos, un pipeline de generación de libros, un flujo de conversión de documentos).

No usar esta skill para crear PDFs, Word (.docx) o PowerPoint (.pptx) — para eso existen las skills `pdf`, `docx` y `pptx` respectivamente. Esta skill es exclusivamente para producir `.epub` de salida.

## Cómo usarla

Todo el trabajo lo hace un solo script, `scripts/build_epub.py`. No hay que escribir código de parsing ni de empaquetado a mano — invocarlo por línea de comandos.

```bash
python3 scripts/build_epub.py \
  --input "ruta/al/documento.pdf" \
  --output "ruta/de/salida/Libro.epub" \
  --title "Título del libro" \
  --author "Nombre del autor" \
  [--language es] \
  [--description "Descripción breve"] \
  [--rights "Aviso de derechos, si corresponde"] \
  [--mode auto|dialogue|chapters|flow] \
  [--css ruta/a/estilo.css] \
  [--cover ruta/a/portada.jpg] \
  [--words-per-section 1800]
```

Parámetros clave:

- `--input`: acepta `.pdf`, `.txt` o `.md`. Para PDF usa `pdfplumber` (si no está instalado: `pip install pdfplumber --break-system-packages`).
- `--title` / `--author`: siempre pedirlos o inferirlos del propio documento (portada, metadatos) antes de correr el script — no dejar "Desconocido" si el documento trae esa información visible.
- `--rights`: si el documento original indica derechos reservados o restricciones de reproducción, pasarlos aquí para que queden en la portada y en los metadatos del EPUB. No omitir este dato si está presente en el original.
- `--mode auto` (default): detecta solo el formato. Forzar `dialogue`, `chapters` o `flow` sólo si la autodetección da un resultado incorrecto (ver "Modos" abajo).
- `--css`: por defecto usa una hoja de estilos incluida (`assets/style.css`) pensada para lectura de guiones y prosa. Pasar una propia sólo si el usuario pide una estética distinta.

### Flujo de trabajo recomendado

1. Confirmar (o inferir del propio archivo) título, autor y, si corresponde, un aviso de derechos.
2. Correr el script con `--mode auto` primero.
3. Revisar el mensaje de stderr `[build_epub] Modo detectado/usado: ...` — si el documento es claramente un guion y detectó `chapters` o `flow` (o viceversa), re-ejecutar forzando `--mode`.
4. Abrir 1-2 archivos `OEBPS/text/chapterN.xhtml` dentro del `.epub` (es un zip) para verificar que el contenido se ve bien formateado antes de entregarlo.
5. Presentar el `.epub` al usuario con la herramienta de archivos disponible (nunca dejarlo sólo en el filesystem sin mostrarlo).

## Modos de detección

- **dialogue**: guiones de teatro/cine. Detecta líneas `Nombre.- texto` junto con encabezados de escena (`Escena N`, `ESCENA N`, `Acto N`, `N – ...`) y agrupadores de parte/acto (`PARTE N`). Cada escena se vuelca en un capítulo del EPUB, con el nombre del personaje en versalitas/negrita.
- **chapters**: prosa con capítulos marcados — encabezados Markdown (`#`, `##`), "Capítulo N" / "CAPÍTULO N" / "Chapter N", números romanos solos en una línea, o líneas cortas en mayúsculas. Cada capítulo detectado se vuelca en un capítulo del EPUB.
- **flow**: texto sin estructura reconocible. Se trocea en secciones de tamaño legible (`--words-per-section`, 1800 palabras por defecto) tituladas "Sección N", para que ningún capítulo del ereader quede monolítico.

Si un documento mezcla formatos (por ejemplo, un libro con capítulos que a su vez contienen diálogos de guion), usar `chapters` — el diálogo dentro de un capítulo de prosa se sigue leyendo bien como texto corrido; no hace falta el modo `dialogue` salvo que el documento entero sea un guion teatral/cinematográfico.

## Limitaciones conocidas

- La extracción de PDF depende de que el texto sea seleccionable (no escaneado/imagen). Para PDFs escaneados, usar primero la skill `pdf` (OCR) y pasar el resultado como `.txt`.
- El detector de capítulos es heurístico: en textos con títulos de capítulo poco convencionales puede fallar y caer a `flow` — en ese caso forzar `--mode chapters` no ayuda si no hay líneas que calcen con los patrones; en ese caso es más simple pre-marcar los capítulos con `# Título` en un `.md` intermedio.
- No genera imagen de portada — si se quiere una portada ilustrada, generarla aparte y pasarla con `--cover`.

## Referencia

- `scripts/build_epub.py` — script único, autocontenido, con extracción + detección + render + empaquetado.
- `assets/style.css` — hoja de estilos por defecto (también embebida como fallback dentro del script).
