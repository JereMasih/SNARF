import fitz

from snarf.capabilities import pdf_extractor as module
from snarf.capabilities.pdf_extractor import PdfExtractor


def make_pdf_bytes(pages_text: list[str | None]) -> bytes:
    """Construye un PDF real con PyMuPDF. `None` deja la página sin texto
    (simula un escaneo puro, sin capa de texto)."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text is not None:
            page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_text_from_a_pdf_with_a_real_text_layer():
    pdf_bytes = make_pdf_bytes(["hola mundo, esto es un PDF con texto real"])
    text = PdfExtractor().extract_text(pdf_bytes)
    assert "hola mundo" in text


def test_extract_text_handles_multiple_pages_without_crashing():
    pdf_bytes = make_pdf_bytes(["página uno", "página dos", "página tres"])
    text = PdfExtractor().extract_text(pdf_bytes)
    assert "página uno" in text
    assert "página tres" in text


def test_is_always_available_no_credentials_needed():
    assert PdfExtractor().available is True


def test_ocr_available_reflects_whether_tesseract_binary_is_on_path(monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: "/opt/homebrew/bin/tesseract")
    assert PdfExtractor().ocr_available is True

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    assert PdfExtractor().ocr_available is False


def test_extract_text_falls_back_to_ocr_when_pdf_has_no_real_text_layer(monkeypatch):
    # Simula un PDF escaneado (sin texto nativo, solo una página en blanco) —
    # PyMuPDF no encuentra nada, así que debería intentar OCR.
    monkeypatch.setattr(module.shutil, "which", lambda name: "/opt/homebrew/bin/tesseract")
    monkeypatch.setattr(module.pytesseract, "image_to_string", lambda image, lang: "texto reconocido por ocr")

    pdf_bytes = make_pdf_bytes([None])
    text = PdfExtractor().extract_text(pdf_bytes)

    assert text == "texto reconocido por ocr"


def test_extract_text_skips_ocr_when_tesseract_is_not_installed(monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    def boom(*args, **kwargs):
        raise AssertionError("no debería llamar a pytesseract si tesseract no está instalado")

    monkeypatch.setattr(module.pytesseract, "image_to_string", boom)

    pdf_bytes = make_pdf_bytes([None])
    text = PdfExtractor().extract_text(pdf_bytes)

    assert text == ""


def test_extract_text_does_not_run_ocr_when_native_text_is_already_real(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("no debería llamar a OCR si ya hay texto nativo real")

    monkeypatch.setattr(module.shutil, "which", lambda name: "/opt/homebrew/bin/tesseract")
    monkeypatch.setattr(module.pytesseract, "image_to_string", boom)

    pdf_bytes = make_pdf_bytes(["un párrafo largo con texto nativo real, más de veinte caracteres seguro"])
    text = PdfExtractor().extract_text(pdf_bytes)

    assert "párrafo largo" in text


def test_extract_text_falls_back_to_the_poor_native_text_if_ocr_finds_nothing(monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: "/opt/homebrew/bin/tesseract")
    monkeypatch.setattr(module.pytesseract, "image_to_string", lambda image, lang: "")

    pdf_bytes = make_pdf_bytes(["hi"])  # muy poco texto nativo, dispara el intento de OCR
    text = PdfExtractor().extract_text(pdf_bytes)

    assert text == "hi"
