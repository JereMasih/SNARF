import io

from pypdf import PdfReader

from snarf.capabilities.base import Capability


class PdfExtractor(Capability):
    name = "pdf_extractor"

    @property
    def available(self) -> bool:
        return True

    def extract_text(self, pdf_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
