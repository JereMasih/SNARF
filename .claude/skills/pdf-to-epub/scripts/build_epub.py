#!/usr/bin/env python3
"""
build_epub.py — Convierte un PDF, TXT o Markdown en un EPUB3 válido.

Detecta automáticamente la estructura del documento:
  - "dialogue": guiones teatrales / de cine con líneas "Nombre.- texto" y
    encabezados de escena/acto ("Escena 3", "ESCENA 3", "3 – ...", "ACTO II").
  - "chapters": prosa con capítulos marcados (encabezados Markdown "# ",
    "Capítulo N", "CAPÍTULO N", "Chapter N", números romanos solos en una
    línea, etc.)
  - "flow": texto corrido sin estructura detectable — se trocea en
    secciones de tamaño razonable para que el lector no cargue un solo
    archonolítico.

Uso:
    python build_epub.py --input libro.pdf --output libro.epub \
        --title "Título" --author "Autor" [--language es] \
        [--mode auto|dialogue|chapters|flow] [--css ruta/style.css] \
        [--description "..."] [--cover ruta/portada.jpg]

Dependencias: pdfplumber (sólo si --input es .pdf). El resto es stdlib.
"""

import argparse
import html
import json
import os
import re
import sys
import uuid
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------
# 1. EXTRACCIÓN DE TEXTO
# --------------------------------------------------------------------------

def extract_pdf_text(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        sys.exit(
            "Falta pdfplumber para leer PDFs. Instalar con:\n"
            "  pip install pdfplumber --break-system-packages"
        )
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    # \f (form feed) separa páginas — se usa como pista para descartar
    # números de página sueltos más adelante.
    return "\f".join(pages)


def load_source_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    # txt / md / cualquier texto plano
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


# --------------------------------------------------------------------------
# 2. LIMPIEZA DE LÍNEAS
# --------------------------------------------------------------------------

PAGE_NUM_RE = re.compile(r"^\d{1,4}$")
DOTTED_TOC_RE = re.compile(r"\.{5,}\s*\d{1,4}\s*$")  # "Capítulo 3....... 12"


def clean_lines(raw: str) -> list[str]:
    lines: list[str] = []
    for page in raw.split("\f"):
        for ln in page.split("\n"):
            s = ln.rstrip()
            stripped = s.strip()
            if stripped == "":
                continue
            if PAGE_NUM_RE.match(stripped):
                continue
            if DOTTED_TOC_RE.search(stripped):
                # línea de índice con puntos de relleno -> se descarta,
                # el índice real lo genera el propio EPUB.
                continue
            lines.append(stripped)
    return lines


# --------------------------------------------------------------------------
# 3. DETECCIÓN DE FORMATO
# --------------------------------------------------------------------------

DIALOGUE_NAME_RE = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜñáéíóúü\s]{0,28}\.-\s")
SCENE_WORD_RE = re.compile(r"^(Escena|ESCENA|Acto|ACTO|Cuadro|CUADRO)\b")
SCENE_NUM_RE = re.compile(r"^(\d{1,3})\s*[–-]\s")
PARTE_RE = re.compile(r"^(PARTE|Parte)\s")

MD_HEADER_RE = re.compile(r"^#{1,3}\s+\S")
CHAPTER_WORD_RE = re.compile(
    r"^(Cap[ií]tulo|CAP[IÍ]TULO|Chapter|CHAPTER|Parte|PARTE)\s+\S", re.UNICODE
)
ROMAN_ONLY_RE = re.compile(r"^[IVXLCDM]{1,8}\.?$")
ALLCAPS_SHORT_RE = re.compile(r"^[A-ZÁÉÍÓÚÑÜ0-9 .,:'\-]{4,60}$")


def detect_mode(lines: list[str]) -> str:
    if not lines:
        return "flow"
    sample = lines[: min(len(lines), 400)]
    dialogue_hits = sum(1 for ln in sample if DIALOGUE_NAME_RE.match(ln))
    scene_hits = sum(
        1
        for ln in sample
        if SCENE_WORD_RE.match(ln) or SCENE_NUM_RE.match(ln) or PARTE_RE.match(ln)
    )
    if dialogue_hits >= max(6, len(sample) * 0.06) and scene_hits >= 1:
        return "dialogue"

    chapter_hits = sum(
        1
        for ln in lines
        if MD_HEADER_RE.match(ln)
        or CHAPTER_WORD_RE.match(ln)
        or ROMAN_ONLY_RE.match(ln)
        or (ALLCAPS_SHORT_RE.match(ln) and len(ln.split()) <= 8)
    )
    if chapter_hits >= 2:
        return "chapters"

    return "flow"


# --------------------------------------------------------------------------
# 4a. MODO DIÁLOGO (guiones)
# --------------------------------------------------------------------------

def parse_dialogue(lines: list[str]):
    """Devuelve lista de escenas: {'title': str, 'blocks': [(tipo, texto)]}."""
    blocks = []
    cur_type = None
    cur_text = ""

    def flush():
        nonlocal cur_text, cur_type
        if cur_text.strip():
            blocks.append((cur_type, cur_text.strip()))
        cur_text, cur_type = "", None

    for ln in lines:
        if PARTE_RE.match(ln):
            flush()
            blocks.append(("parte", ln.strip()))
            continue
        if SCENE_WORD_RE.match(ln):
            flush()
            blocks.append(("scene", ln.strip()))
            continue
        if SCENE_NUM_RE.match(ln):
            flush()
            blocks.append(("scene", "Escena " + ln.strip()))
            continue
        if DIALOGUE_NAME_RE.match(ln):
            flush()
            cur_type, cur_text = "dialogue", ln
            continue
        if ln.startswith("("):
            flush()
            cur_type, cur_text = "direction", ln
            continue
        if cur_text:
            cur_text += " " + ln
        else:
            cur_type, cur_text = "direction", ln
    flush()

    scenes = []
    cur_scene = None
    cur_part = None
    for btype, text in blocks:
        if btype == "parte":
            cur_part = text
            continue
        if btype == "scene":
            cur_scene = {"title": text, "part": cur_part, "blocks": []}
            scenes.append(cur_scene)
            continue
        if cur_scene is None:
            # Texto anterior al primer encabezado de escena real (portada,
            # datos del autor, etc. capturados por el PDF) — se descarta,
            # ya que título/autor se pasan explícitamente por CLI.
            continue
        cur_scene["blocks"].append((btype, text))
    return scenes


def render_dialogue_scene_html(scene: dict) -> str:
    parts = []
    title = scene["title"]
    m = re.match(r"^(Escena\s*\d+|Acto\s*\d+|Cuadro\s*\d+)[\s.:–-]*(.*)$", title, re.I)
    if m:
        heading, subtitle = m.group(1), m.group(2).strip(" .–-")
    else:
        heading, subtitle = title, ""
    parts.append(f"<h2>{html.escape(heading)}</h2>")
    if subtitle:
        subtitle = subtitle.split("(")[0].strip(" .–-")
        if subtitle:
            parts.append(f'<p class="scene-subtitle">{html.escape(subtitle)}</p>')
    for btype, text in scene["blocks"]:
        if btype == "dialogue":
            m2 = re.match(r"^([^.]+?)\.-\s*(.*)$", text)
            if m2:
                name, rest = m2.group(1), m2.group(2)
                parts.append(
                    f'<p class="dlg"><span class="name">{html.escape(name)}.-</span> '
                    f"{html.escape(rest)}</p>"
                )
            else:
                parts.append(f'<p class="dlg">{html.escape(text)}</p>')
        else:
            parts.append(f'<p class="dir">{html.escape(text)}</p>')
    return "\n".join(parts)


# --------------------------------------------------------------------------
# 4b. MODO CAPÍTULOS (prosa)
# --------------------------------------------------------------------------

def parse_chapters(lines: list[str]):
    chapters = []
    cur = None

    def is_header(ln):
        return (
            MD_HEADER_RE.match(ln)
            or CHAPTER_WORD_RE.match(ln)
            or ROMAN_ONLY_RE.match(ln)
            or (ALLCAPS_SHORT_RE.match(ln) and len(ln.split()) <= 8)
        )

    paragraph = ""
    for ln in lines:
        if is_header(ln):
            if paragraph.strip() and cur is not None:
                cur["paragraphs"].append(paragraph.strip())
            paragraph = ""
            title = re.sub(r"^#{1,3}\s+", "", ln).strip()
            cur = {"title": title, "paragraphs": []}
            chapters.append(cur)
            continue
        if cur is None:
            cur = {"title": "", "paragraphs": []}
            chapters.append(cur)
        paragraph += (" " if paragraph else "") + ln
        # Heurística simple de fin de párrafo: si la línea termina en
        # puntuación fuerte y la siguiente pinta a nueva oración larga,
        # igual lo dejamos fluir — el PDF ya viene sin saltos de párrafo
        # reales en la mayoría de los casos, así que cada "bloque" entre
        # headers se vuelca como un único párrafo continuo salvo que el
        # propio texto traiga líneas en blanco (ya filtradas). Se corta
        # cada ~120 palabras para longitud de lectura razonable.
        if len(paragraph.split()) > 120:
            cur["paragraphs"].append(paragraph.strip())
            paragraph = ""
    if paragraph.strip() and cur is not None:
        cur["paragraphs"].append(paragraph.strip())
    return chapters


def render_chapter_html(chapter: dict) -> str:
    parts = []
    if chapter["title"]:
        parts.append(f"<h2>{html.escape(chapter['title'])}</h2>")
    for p in chapter["paragraphs"]:
        parts.append(f"<p>{html.escape(p)}</p>")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# 4c. MODO FLUJO (sin estructura detectable)
# --------------------------------------------------------------------------

def parse_flow(lines: list[str], words_per_section: int = 1800):
    sections = []
    cur_words = 0
    cur_paras: list[str] = []
    paragraph = ""

    def close_paragraph():
        nonlocal paragraph
        if paragraph.strip():
            cur_paras.append(paragraph.strip())
        paragraph = ""

    for ln in lines:
        paragraph += (" " if paragraph else "") + ln
        if len(paragraph.split()) > 120:
            close_paragraph()
        cur_words += len(ln.split())
        if cur_words >= words_per_section:
            close_paragraph()
            sections.append({"title": "", "paragraphs": list(cur_paras)})
            cur_paras, cur_words = [], 0
    close_paragraph()
    if cur_paras:
        sections.append({"title": "", "paragraphs": cur_paras})
    for i, s in enumerate(sections, start=1):
        s["title"] = f"Sección {i}"
    return sections


# --------------------------------------------------------------------------
# 5. EMPAQUETADO EPUB3
# --------------------------------------------------------------------------

DEFAULT_CSS = """@charset "UTF-8";
body { font-family: Georgia, "Palatino Linotype", serif; line-height: 1.5; margin: 1em 1.2em; color: #1a1a1a; }
.titlepage { text-align: center; margin-top: 3em; }
.titlepage h1 { font-size: 2em; margin-bottom: 0.3em; }
.titlepage .subtitle { font-style: italic; font-size: 1.1em; margin-bottom: 1.5em; }
.titlepage .author { font-size: 1.05em; margin-bottom: 2.5em; }
.titlepage .rights { font-size: 0.75em; color: #555; margin-top: 3em; border-top: 1px solid #ccc; padding-top: 1em; }
.toc-page h2 { text-align: center; margin-bottom: 1em; }
.tocline { margin: 0.3em 0; }
.tocline a { text-decoration: none; color: #1a1a1a; }
.parte-marker { text-align: center; text-transform: uppercase; letter-spacing: 0.15em; font-size: 0.85em; color: #666; margin: 2em 0 0.5em 0; border-top: 1px solid #ccc; padding-top: 1em; }
h2 { text-align: center; font-size: 1.4em; margin-top: 0.4em; margin-bottom: 0.1em; }
.scene-subtitle { text-align: center; font-style: italic; color: #555; margin-top: 0; margin-bottom: 1.4em; font-size: 0.95em; }
p { margin: 0 0 0.9em 0; text-align: justify; }
p.dlg { margin: 0 0 0.7em 0; text-align: justify; }
p.dlg .name { font-weight: bold; font-variant: small-caps; }
p.dir { margin: 0.8em 0; font-style: italic; color: #444; text-align: center; font-size: 0.92em; }
"""


def build_epub(
    output_path: str,
    title: str,
    author: str,
    language: str,
    description: str,
    rights: str,
    chapter_htmls: list[tuple],  # (nav_title, body_html, part_label_or_None)
    css: str = None,
    cover_image_path: str = None,
):
    css = css or DEFAULT_CSS
    tmp_root = Path(output_path).with_suffix("") .as_posix() + "_epub_build"
    tmp_root = Path(tmp_root)
    if tmp_root.exists():
        import shutil
        shutil.rmtree(tmp_root)
    oebps = tmp_root / "OEBPS"
    text_dir = oebps / "text"
    styles_dir = oebps / "styles"
    text_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)
    (tmp_root / "META-INF").mkdir(parents=True, exist_ok=True)

    (tmp_root / "mimetype").write_text("application/epub+zip", encoding="utf-8")
    (tmp_root / "META-INF" / "container.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles>\n'
        '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        '  </rootfiles>\n'
        "</container>\n",
        encoding="utf-8",
    )
    (styles_dir / "style.css").write_text(css, encoding="utf-8")

    manifest_items = []
    spine_items = []
    nav_entries = []

    cover_manifest = ""
    cover_body = ""
    if cover_image_path and Path(cover_image_path).exists():
        ext = Path(cover_image_path).suffix.lower().lstrip(".")
        media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        import shutil as _sh
        _sh.copy(cover_image_path, oebps / f"cover.{ext}")
        cover_manifest = f'    <item id="cover-img" href="cover.{ext}" media-type="{media}" properties="cover-image"/>\n'

    # Portada / título
    rights_html = f'<p class="rights">{html.escape(rights)}</p>' if rights else ""
    title_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}" lang="{language}">
<head><title>{html.escape(title)}</title><link rel="stylesheet" type="text/css" href="../styles/style.css"/></head>
<body>
<section class="titlepage">
<h1>{html.escape(title)}</h1>
<p class="author">{html.escape(author)}</p>
{rights_html}
</section>
</body>
</html>"""
    (text_dir / "title.xhtml").write_text(title_html, encoding="utf-8")
    manifest_items.append(("title", "text/title.xhtml", "application/xhtml+xml"))
    spine_items.append("title")
    nav_entries.append(("Portada", "text/title.xhtml", None))

    # Índice
    toc_lines = []
    last_part = object()
    for i, (nav_title, _, part_label) in enumerate(chapter_htmls, start=1):
        if part_label != last_part and part_label:
            toc_lines.append(f"<h3>{html.escape(part_label)}</h3>")
        last_part = part_label
        toc_lines.append(
            f'<p class="tocline"><a href="chapter{i}.xhtml">{html.escape(nav_title)}</a></p>'
        )
    toc_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}" lang="{language}">
<head><title>Índice</title><link rel="stylesheet" type="text/css" href="../styles/style.css"/></head>
<body><section class="toc-page"><h2>Índice</h2>
{''.join(toc_lines)}
</section></body>
</html>"""
    (text_dir / "contents.xhtml").write_text(toc_html, encoding="utf-8")
    manifest_items.append(("contents", "text/contents.xhtml", "application/xhtml+xml"))
    spine_items.append("contents")
    nav_entries.append(("Índice", "text/contents.xhtml", None))

    # Capítulos
    last_part = object()
    for i, (nav_title, body_html, part_label) in enumerate(chapter_htmls, start=1):
        fname = f"chapter{i}.xhtml"
        part_marker = ""
        if part_label != last_part and part_label:
            part_marker = f'<p class="parte-marker">{html.escape(part_label)}</p>'
        last_part = part_label
        chap_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}" lang="{language}">
<head><title>{html.escape(nav_title)}</title><link rel="stylesheet" type="text/css" href="../styles/style.css"/></head>
<body><section epub:type="chapter" xmlns:epub="http://www.idpf.org/2007/ops">
{part_marker}
{body_html}
</section></body>
</html>"""
        (text_dir / fname).write_text(chap_html, encoding="utf-8")
        manifest_items.append((f"chapter{i}", f"text/{fname}", "application/xhtml+xml"))
        spine_items.append(f"chapter{i}")
        nav_entries.append((nav_title, f"text/{fname}", part_label))

    # nav.xhtml
    nav_li = []
    for nav_title, href, _ in nav_entries:
        nav_li.append(f'<li><a href="{href}">{html.escape(nav_title)}</a></li>')
    nav_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{language}" lang="{language}">
<head><title>Navegación</title><link rel="stylesheet" type="text/css" href="styles/style.css"/></head>
<body><nav epub:type="toc" id="toc"><h1>Contenido</h1><ol>
{''.join(nav_li)}
</ol></nav></body>
</html>"""
    (oebps / "nav.xhtml").write_text(nav_html, encoding="utf-8")

    # toc.ncx (compatibilidad EPUB2)
    navpoints = []
    for order, (nav_title, href, _) in enumerate(nav_entries, start=1):
        navpoints.append(
            f'<navPoint id="np-{order}" playOrder="{order}"><navLabel><text>{html.escape(nav_title)}</text></navLabel><content src="{href}"/></navPoint>'
        )
    uid = f"urn:uuid:{uuid.uuid4()}"
    ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{uid}"/><meta name="dtb:depth" content="1"/>
  <meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>
  <docTitle><text>{html.escape(title)}</text></docTitle>
  <navMap>
{chr(10).join(navpoints)}
  </navMap>
</ncx>
"""
    (oebps / "toc.ncx").write_text(ncx, encoding="utf-8")

    # content.opf
    manifest_xml = [
        f'    <item id="{iid}" href="{href}" media-type="{mt}"/>'
        for iid, href, mt in manifest_items
    ]
    manifest_xml.append('    <item id="style" href="styles/style.css" media-type="text/css"/>')
    manifest_xml.append(
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    )
    manifest_xml.append('    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
    if cover_manifest:
        manifest_xml.append(cover_manifest.strip())
    spine_xml = [f'    <itemref idref="{s}"/>' for s in spine_items]
    desc_xml = f"<dc:description>{html.escape(description)}</dc:description>" if description else ""
    rights_xml = f"<dc:rights>{html.escape(rights)}</dc:rights>" if rights else ""
    opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id" xml:lang="{language}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">{uid}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    <dc:language>{language}</dc:language>
    {desc_xml}
    {rights_xml}
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest_xml)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_xml)}
  </spine>
</package>
"""
    (oebps / "content.opf").write_text(opf, encoding="utf-8")

    # Zippear: mimetype primero y sin compresión
    out = Path(output_path)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w") as zf:
        zf.write(tmp_root / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for root, _, files in os.walk(tmp_root):
            for fn in files:
                full = Path(root) / fn
                rel = full.relative_to(tmp_root)
                if rel.as_posix() == "mimetype":
                    continue
                zf.write(full, rel.as_posix(), compress_type=zipfile.ZIP_DEFLATED)

    import shutil
    shutil.rmtree(tmp_root)
    return out


# --------------------------------------------------------------------------
# 6. CLI
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Convierte PDF/TXT/MD a EPUB3.")
    ap.add_argument("--input", required=True, help="Ruta al .pdf, .txt o .md de entrada")
    ap.add_argument("--output", required=True, help="Ruta del .epub de salida")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", default="Desconocido")
    ap.add_argument("--language", default="es")
    ap.add_argument("--description", default="")
    ap.add_argument("--rights", default="")
    ap.add_argument(
        "--mode",
        choices=["auto", "dialogue", "chapters", "flow"],
        default="auto",
        help="Forzar el modo de estructura en vez de autodetectarlo",
    )
    ap.add_argument("--css", default=None, help="Ruta a un .css alternativo")
    ap.add_argument("--cover", default=None, help="Ruta a imagen de portada (jpg/png)")
    ap.add_argument(
        "--words-per-section",
        type=int,
        default=1800,
        help="Sólo para modo flow: tamaño aproximado de cada sección",
    )
    args = ap.parse_args()

    raw = load_source_text(args.input)
    lines = clean_lines(raw)

    mode = args.mode
    if mode == "auto":
        mode = detect_mode(lines)
    print(f"[build_epub] Modo detectado/usado: {mode}", file=sys.stderr)

    chapter_htmls = []  # (nav_title, body_html, part_label)

    if mode == "dialogue":
        scenes = parse_dialogue(lines)
        for sc in scenes:
            body = render_dialogue_scene_html(sc)
            nav_title = sc["title"].split("(")[0].strip(" .–-") or "Escena"
            chapter_htmls.append((nav_title, body, sc.get("part")))
    elif mode == "chapters":
        chapters = parse_chapters(lines)
        for i, ch in enumerate(chapters, start=1):
            body = render_chapter_html(ch)
            nav_title = ch["title"] or f"Capítulo {i}"
            chapter_htmls.append((nav_title, body, None))
    else:  # flow
        sections = parse_flow(lines, words_per_section=args.words_per_section)
        for sec in sections:
            body = render_chapter_html(sec)
            chapter_htmls.append((sec["title"], body, None))

    if not chapter_htmls:
        sys.exit("[build_epub] No se pudo extraer contenido del documento de entrada.")

    css = None
    if args.css:
        css = Path(args.css).read_text(encoding="utf-8")

    out = build_epub(
        output_path=args.output,
        title=args.title,
        author=args.author,
        language=args.language,
        description=args.description,
        rights=args.rights,
        chapter_htmls=chapter_htmls,
        css=css,
        cover_image_path=args.cover,
    )
    print(f"[build_epub] EPUB generado: {out}")


if __name__ == "__main__":
    main()
