import html
import io
import re
import uuid
import zipfile
from pathlib import Path

from snarf.capabilities.base import Capability

# --------------------------------------------------------------------------
# Lógica portada de la skill de Claude Code `pdf-to-epub`
# (.claude/skills/pdf-to-epub/scripts/build_epub.py, probada de punta a punta
# en la misma sesión que esta capacidad) — misma detección de estructura y
# mismo armado de EPUB3, adaptada a bytes en memoria (BytesIO in/out) en vez
# de rutas de archivo/directorio temporal, para poder correr sin tocar el
# filesystem dentro de un server con requests concurrentes.
# --------------------------------------------------------------------------

PAGE_NUM_RE = re.compile(r"^\d{1,4}$")
DOTTED_TOC_RE = re.compile(r"\.{5,}\s*\d{1,4}\s*$")  # "Capítulo 3....... 12"

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


def _extract_pdf_text(data: bytes) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    # \f (form feed) separa páginas — se usa como pista para descartar
    # números de página sueltos más adelante.
    return "\f".join(pages)


def _load_source_text(data: bytes, suffix: str) -> str:
    if suffix == ".pdf":
        return _extract_pdf_text(data)
    return data.decode("utf-8", errors="replace")


def _clean_lines(raw: str) -> list[str]:
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
                continue
            lines.append(stripped)
    return lines


def _detect_mode(lines: list[str]) -> str:
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


def _parse_dialogue(lines: list[str]):
    """Devuelve lista de escenas: {'title': str, 'part': str|None, 'blocks': [(tipo, texto)]}."""
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
            # datos del autor, etc.) — se descarta, título/autor se pasan
            # explícitamente.
            continue
        cur_scene["blocks"].append((btype, text))
    return scenes


def _render_dialogue_scene_html(scene: dict) -> str:
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


def _parse_chapters(lines: list[str]):
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
        # Heurística de fin de párrafo: cada "bloque" entre headers se vuelca
        # como un párrafo continuo, cortado cada ~120 palabras para longitud
        # de lectura razonable (el texto fuente rara vez trae saltos reales).
        if len(paragraph.split()) > 120:
            cur["paragraphs"].append(paragraph.strip())
            paragraph = ""
    if paragraph.strip() and cur is not None:
        cur["paragraphs"].append(paragraph.strip())
    return chapters


def _render_chapter_html(chapter: dict) -> str:
    parts = []
    if chapter["title"]:
        parts.append(f"<h2>{html.escape(chapter['title'])}</h2>")
    for p in chapter["paragraphs"]:
        parts.append(f"<p>{html.escape(p)}</p>")
    return "\n".join(parts)


def _parse_flow(lines: list[str], words_per_section: int = 1800):
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


def _build_epub_bytes(
    title: str,
    author: str,
    language: str,
    description: str,
    rights: str,
    chapter_htmls: list[tuple],  # (nav_title, body_html, part_label_or_None)
    css: str | None = None,
) -> bytes:
    css = css or DEFAULT_CSS
    manifest_items = []
    spine_items = []
    nav_entries = []

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
    manifest_items.append(("title", "text/title.xhtml", "application/xhtml+xml"))
    spine_items.append("title")
    nav_entries.append(("Portada", "text/title.xhtml", None))

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
    manifest_items.append(("contents", "text/contents.xhtml", "application/xhtml+xml"))
    spine_items.append("contents")
    nav_entries.append(("Índice", "text/contents.xhtml", None))

    chapter_files = {}
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
        chapter_files[fname] = chap_html
        manifest_items.append((f"chapter{i}", f"text/{fname}", "application/xhtml+xml"))
        spine_items.append(f"chapter{i}")
        nav_entries.append((nav_title, f"text/{fname}", part_label))

    nav_li = [f'<li><a href="{href}">{html.escape(nav_title)}</a></li>' for nav_title, href, _ in nav_entries]
    nav_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{language}" lang="{language}">
<head><title>Navegación</title><link rel="stylesheet" type="text/css" href="styles/style.css"/></head>
<body><nav epub:type="toc" id="toc"><h1>Contenido</h1><ol>
{''.join(nav_li)}
</ol></nav></body>
</html>"""

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

    manifest_xml = [f'    <item id="{iid}" href="{href}" media-type="{mt}"/>' for iid, href, mt in manifest_items]
    manifest_xml.append('    <item id="style" href="styles/style.css" media-type="text/css"/>')
    manifest_xml.append('    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    manifest_xml.append('    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
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
  </metadata>
  <manifest>
{chr(10).join(manifest_xml)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_xml)}
  </spine>
</package>
"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype primero y sin comprimir — requisito del formato EPUB.
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            '  <rootfiles>\n'
            '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
            '  </rootfiles>\n'
            "</container>\n",
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr("OEBPS/styles/style.css", css, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/text/title.xhtml", title_html, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/text/contents.xhtml", toc_html, compress_type=zipfile.ZIP_DEFLATED)
        for fname, chap_html in chapter_files.items():
            zf.writestr(f"OEBPS/text/{fname}", chap_html, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", nav_html, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


class EpubBuilder(Capability):
    """Convierte un PDF/TXT/Markdown ya en memoria en un EPUB3 válido —
    misma lógica de detección de estructura (guion/capítulos/flujo) que la
    skill de Claude Code `pdf-to-epub`, portada acá para que el Orchestrator
    tenga su propia capacidad real (ver ADR 0202) sin depender de un sistema
    de skills que no puede invocar en tiempo de ejecución."""

    name = "epub_builder"

    @property
    def available(self) -> bool:
        return True

    def convert(
        self,
        source_bytes: bytes,
        source_name: str,
        title: str,
        author: str,
        mode: str = "auto",
        language: str = "es",
        description: str = "",
        rights: str = "",
        words_per_section: int = 1800,
    ) -> tuple[bytes, str]:
        """Devuelve (epub_bytes, modo_usado). Levanta ValueError si no se
        pudo extraer contenido real del documento fuente (mismo caso límite
        que el script original)."""
        suffix = Path(source_name).suffix.lower()
        if suffix not in (".pdf", ".txt", ".md"):
            suffix = ".pdf"
        raw = _load_source_text(source_bytes, suffix)
        lines = _clean_lines(raw)

        mode_used = mode
        if mode_used == "auto":
            mode_used = _detect_mode(lines)

        chapter_htmls: list[tuple] = []
        if mode_used == "dialogue":
            for scene in _parse_dialogue(lines):
                body = _render_dialogue_scene_html(scene)
                nav_title = scene["title"].split("(")[0].strip(" .–-") or "Escena"
                chapter_htmls.append((nav_title, body, scene.get("part")))
        elif mode_used == "chapters":
            for i, chapter in enumerate(_parse_chapters(lines), start=1):
                body = _render_chapter_html(chapter)
                nav_title = chapter["title"] or f"Capítulo {i}"
                chapter_htmls.append((nav_title, body, None))
        else:  # flow
            for section in _parse_flow(lines, words_per_section=words_per_section):
                body = _render_chapter_html(section)
                chapter_htmls.append((section["title"], body, None))

        if not chapter_htmls:
            raise ValueError("no se pudo extraer contenido del documento de entrada")

        epub_bytes = _build_epub_bytes(title, author, language, description, rights, chapter_htmls)
        return epub_bytes, mode_used
