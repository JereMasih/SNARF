from snarf.capabilities.document_builder import DocumentBuilder
from snarf.capabilities.pdf_extractor import PdfExtractor
from snarf.capabilities.pptx_extractor import PptxExtractor
from snarf.capabilities.xlsx_extractor import XlsxExtractor


def test_build_markdown_includes_title_and_content():
    content = DocumentBuilder().build_markdown("Mi Titulo", "cuerpo real del documento").decode("utf-8")
    assert "# Mi Titulo" in content
    assert "cuerpo real del documento" in content


def test_build_markdown_without_title_is_just_the_content():
    content = DocumentBuilder().build_markdown("", "solo el cuerpo").decode("utf-8")
    assert content == "solo el cuerpo"


def test_build_pdf_roundtrips_through_the_real_extractor():
    pdf_bytes = DocumentBuilder().build_pdf("Reporte de Trading", "Contenido real del reporte.")
    text = PdfExtractor().extract_text(pdf_bytes)
    assert "Reporte de Trading" in text
    assert "Contenido real del reporte." in text


def test_build_pptx_roundtrips_through_the_real_extractor():
    pptx_bytes = DocumentBuilder().build_pptx(
        "Titulo Presentacion", [{"title": "Slide 1", "body": "contenido de la diapositiva"}]
    )
    text = PptxExtractor().extract_text(pptx_bytes)
    assert "Titulo Presentacion" in text
    assert "contenido de la diapositiva" in text


def test_build_xlsx_roundtrips_through_the_real_extractor():
    xlsx_bytes = DocumentBuilder().build_xlsx("Hoja", [["nombre", "monto"], ["gasto real", 123]])
    text = XlsxExtractor().extract_text(xlsx_bytes)
    assert "gasto real" in text
    assert "123" in text


def test_is_always_available():
    assert DocumentBuilder().available is True
