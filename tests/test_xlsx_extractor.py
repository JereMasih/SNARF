import io

from openpyxl import Workbook

from snarf.capabilities.xlsx_extractor import XlsxExtractor


def make_xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["nombre", "monto"])
    sheet.append(["gasto real", 123])
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def test_extract_text_includes_cell_values():
    text = XlsxExtractor().extract_text(make_xlsx_bytes())
    assert "nombre" in text
    assert "gasto real" in text
    assert "123" in text


def test_is_always_available():
    assert XlsxExtractor().available is True
