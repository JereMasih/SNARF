import shutil

import fitz
import pytesseract
from PIL import Image

from snarf.capabilities.base import Capability

TESSERACT_BINARY = "tesseract"
OCR_LANGUAGES = "spa+eng"
# Heurística para decidir si el texto nativo es real o ruido: un PDF escaneo
# puro (sin ninguna capa de texto) devuelve prácticamente nada por página.
MIN_CHARS_PER_PAGE_TO_SKIP_OCR = 20


class PdfExtractor(Capability):
    """Extrae texto de PDF vía PyMuPDF, que resuelve el CMap/ToUnicode de
    fuentes Type3 embebidas (comunes en PDFs exportados desde apps móviles o
    navegadores) — pypdf no lo resolvía de forma confiable, devolvía bytes de
    glifo en vez de texto legible. Si el PDF no tiene ninguna capa de texto
    real (un escaneo puro), cae a OCR con Tesseract sobre cada página
    rasterizada por la misma librería, sin necesitar una dependencia aparte."""

    name = "pdf_extractor"

    @property
    def available(self) -> bool:
        return True

    @property
    def ocr_available(self) -> bool:
        return shutil.which(TESSERACT_BINARY) is not None

    def extract_text(self, pdf_bytes: bytes) -> str:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            native_text = "\n\n".join(page.get_text().strip() for page in doc).strip()
            if self._looks_like_real_text(native_text, doc.page_count):
                return native_text
            if not self.ocr_available:
                return native_text
            ocr_text = self._ocr(doc)
            return ocr_text if ocr_text else native_text
        finally:
            doc.close()

    @staticmethod
    def _looks_like_real_text(text: str, page_count: int) -> bool:
        if not text:
            return False
        return len(text) / max(page_count, 1) >= MIN_CHARS_PER_PAGE_TO_SKIP_OCR

    def _ocr(self, doc: "fitz.Document") -> str:
        parts = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            page_text = pytesseract.image_to_string(image, lang=OCR_LANGUAGES).strip()
            if page_text:
                parts.append(page_text)
        return "\n\n".join(parts).strip()
