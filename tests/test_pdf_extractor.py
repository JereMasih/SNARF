import io

from pypdf import PdfWriter

from snarf.capabilities.pdf_extractor import PdfExtractor


def make_pdf_bytes(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extract_text_from_a_valid_pdf_does_not_raise_and_returns_a_string():
    text = PdfExtractor().extract_text(make_pdf_bytes(pages=1))
    assert isinstance(text, str)


def test_extract_text_handles_multiple_pages_without_crashing():
    text = PdfExtractor().extract_text(make_pdf_bytes(pages=3))
    assert isinstance(text, str)


def test_is_always_available_no_credentials_needed():
    assert PdfExtractor().available is True
