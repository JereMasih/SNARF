import io
import zipfile
import xml.etree.ElementTree as ET

import pytest

from snarf.capabilities import epub_builder
from snarf.capabilities.epub_builder import EpubBuilder


def test_detects_dialogue_mode_from_character_names_and_scenes():
    lines = epub_builder._clean_lines(
        "ACTO I\n"
        "Escena 1\n"
        "LILI.- Hola, ¿hay alguien ahí?\n"
        "(silencio)\n"
        "LILI.- Bueno, supongo que no.\n"
        "Escena 2\n"
        "LILI.- Segunda escena, otra vez sola.\n"
        "LILI.- Y otra línea más para pasar el umbral de detección.\n"
        "LILI.- Y otra.\n"
        "LILI.- Y otra más.\n"
    )
    assert epub_builder._detect_mode(lines) == "dialogue"


def test_detects_chapters_mode_from_markdown_headers():
    lines = epub_builder._clean_lines(
        "# Capítulo 1\n"
        "Un párrafo cualquiera de prueba con varias palabras adentro.\n"
        "# Capítulo 2\n"
        "Otro párrafo distinto para el segundo capítulo del libro.\n"
    )
    assert epub_builder._detect_mode(lines) == "chapters"


def test_falls_back_to_flow_mode_for_unstructured_text():
    lines = epub_builder._clean_lines(
        "Esto es un texto corrido sin ningún encabezado ni estructura reconocible, "
        "simplemente prosa continua que sigue y sigue sin marcar nada en particular."
    )
    assert epub_builder._detect_mode(lines) == "flow"


def _assert_valid_epub_zip(epub_bytes: bytes):
    zf = zipfile.ZipFile(io.BytesIO(epub_bytes))
    names = zf.namelist()
    assert names[0] == "mimetype"
    assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    assert zf.read("mimetype") == b"application/epub+zip"
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "OEBPS/nav.xhtml" in names
    assert "OEBPS/toc.ncx" in names
    for name in names:
        if name.endswith(".xhtml") or name.endswith(".xml") or name.endswith(".opf") or name.endswith(".ncx"):
            ET.fromstring(zf.read(name))  # levanta ParseError si no está bien formado
    return zf


def test_convert_from_txt_bytes_produces_a_valid_epub_with_chapters():
    source = (
        "Capitulo 1\n"
        "Primer parrafo de prueba con contenido real para el primer capitulo.\n"
        "Capitulo 2\n"
        "Segundo parrafo de prueba con contenido real para el segundo capitulo.\n"
    ).encode("utf-8")

    epub_bytes, mode_used = EpubBuilder().convert(source, "prueba.txt", "Prueba", "Autor de Prueba")

    assert mode_used == "chapters"
    zf = _assert_valid_epub_zip(epub_bytes)
    assert "OEBPS/text/chapter1.xhtml" in zf.namelist()
    assert "OEBPS/text/chapter2.xhtml" in zf.namelist()
    assert b"Capitulo 1" in zf.read("OEBPS/text/chapter1.xhtml")


def test_convert_from_real_pdf_bytes_produces_a_valid_epub():
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Capitulo 1", fontsize=18)
    page.insert_text((72, 100), "Contenido de prueba del primer capitulo del PDF.", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Capitulo 2", fontsize=18)
    page2.insert_text((72, 100), "Contenido de prueba del segundo capitulo del PDF.", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    epub_bytes, mode_used = EpubBuilder().convert(pdf_bytes, "prueba.pdf", "Prueba PDF", "Autor de Prueba")

    assert mode_used == "chapters"
    _assert_valid_epub_zip(epub_bytes)


def test_convert_raises_value_error_when_no_content_can_be_extracted():
    with pytest.raises(ValueError):
        EpubBuilder().convert(b"   \n\n   ", "vacio.txt", "Título", "Autor")


def test_convert_mode_flow_splits_unstructured_text_into_sections():
    # Muchas líneas cortas (como vendría de un PDF real extraído línea por
    # línea) — un solo string sin saltos de línea no ejercita el chunking,
    # que corta por línea, no por palabra suelta dentro de una línea.
    source = "\n".join("palabra " * 8 for _ in range(500)).encode("utf-8")
    epub_bytes, mode_used = EpubBuilder().convert(source, "prueba.txt", "Prueba", "Autor", words_per_section=1000)
    assert mode_used == "flow"
    zf = _assert_valid_epub_zip(epub_bytes)
    chapter_files = [n for n in zf.namelist() if n.startswith("OEBPS/text/chapter")]
    assert len(chapter_files) >= 2
