from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.knowledge.extraction import ContentExtractor, categorize_mime


class FakeDrive:
    def __init__(self, texts=None, bytes_map=None):
        self._texts = texts or {}
        self._bytes = bytes_map or {}

    def read_file_text(self, file_id, mime_type):
        return self._texts[file_id]

    def read_file_bytes(self, file_id):
        return self._bytes[file_id]


class FakePdf:
    def __init__(self, text="texto del pdf"):
        self.text = text

    def extract_text(self, pdf_bytes):
        return self.text


class FakeVisionLLM:
    def __init__(self, available=True, response="descripción de la imagen"):
        self.available = available
        self.response = response
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        return LLMResponse(text=self.response, speech=self.response)


class FakeStt:
    def __init__(self, available=True, text="transcripción"):
        self.available = available
        self.text = text

    def transcribe(self, audio_bytes):
        return self.text


class FakeFfmpeg:
    def __init__(self, available=True, audio_bytes=b"audio-extraido"):
        self.available = available
        self.audio_bytes = audio_bytes

    def extract_audio(self, video_bytes, suffix=".mp4"):
        return self.audio_bytes


class FakeOfficeExtractor:
    def __init__(self, text="texto de office"):
        self.text = text

    def extract_text(self, file_bytes):
        return self.text


def make_extractor(**overrides):
    vision_llm = overrides.pop("vision_llm", FakeVisionLLM())
    defaults = dict(
        drive=FakeDrive(),
        pdf_extractor=FakePdf(),
        vision_llm_factory=lambda: vision_llm,
        stt=FakeStt(),
        ffmpeg_audio=FakeFfmpeg(),
        docx_extractor=FakeOfficeExtractor("texto de word"),
        pptx_extractor=FakeOfficeExtractor("texto de powerpoint"),
        xlsx_extractor=FakeOfficeExtractor("texto de excel"),
    )
    defaults.update(overrides)
    return ContentExtractor(**defaults)


def test_categorize_mime_covers_all_known_buckets():
    assert categorize_mime("application/vnd.google-apps.folder") == "folder"
    assert categorize_mime("application/vnd.google-apps.document") == "google_doc"
    assert categorize_mime("application/pdf") == "pdf"
    assert categorize_mime("application/vnd.openxmlformats-officedocument.wordprocessingml.document") == "docx"
    assert categorize_mime("application/vnd.openxmlformats-officedocument.presentationml.presentation") == "pptx"
    assert categorize_mime("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == "xlsx"
    assert categorize_mime("text/plain") == "text"
    assert categorize_mime("image/png") == "image"
    assert categorize_mime("audio/mpeg") == "audio"
    assert categorize_mime("video/mp4") == "video"
    assert categorize_mime("application/zip") == "other"


def test_extract_google_doc_reads_text_via_drive():
    extractor = make_extractor(drive=FakeDrive(texts={"d1": "contenido del doc"}))
    result = extractor.extract({"id": "d1", "mimeType": "application/vnd.google-apps.document"})
    assert result.ok
    assert result.text == "contenido del doc"


def test_extract_pdf_uses_pdf_extractor():
    extractor = make_extractor(
        drive=FakeDrive(bytes_map={"p1": b"pdf-bytes"}),
        pdf_extractor=FakePdf(text="texto extraído"),
    )
    result = extractor.extract({"id": "p1", "mimeType": "application/pdf"})
    assert result.text == "texto extraído"


def test_extract_pdf_with_no_usable_text_is_reported_explicitly_not_indexed_empty():
    # Regresión: un PDF escaneado sin capa de texto (ni nativa ni por OCR)
    # devuelve "" — antes eso se indexaba en silencio como si hubiera
    # funcionado; ahora tiene que quedar como no soportado, explícito.
    extractor = make_extractor(
        drive=FakeDrive(bytes_map={"p1": b"pdf-bytes"}),
        pdf_extractor=FakePdf(text=""),
    )
    result = extractor.extract({"id": "p1", "mimeType": "application/pdf"})
    assert not result.ok
    assert "sin texto extraíble" in result.skipped_reason


def test_extract_docx_uses_docx_extractor():
    extractor = make_extractor(drive=FakeDrive(bytes_map={"d1": b"docx-bytes"}))
    result = extractor.extract(
        {"id": "d1", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    )
    assert result.text == "texto de word"


def test_extract_pptx_uses_pptx_extractor():
    extractor = make_extractor(drive=FakeDrive(bytes_map={"p1": b"pptx-bytes"}))
    result = extractor.extract(
        {"id": "p1", "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
    )
    assert result.text == "texto de powerpoint"


def test_extract_xlsx_uses_xlsx_extractor():
    extractor = make_extractor(drive=FakeDrive(bytes_map={"x1": b"xlsx-bytes"}))
    result = extractor.extract(
        {"id": "x1", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    )
    assert result.text == "texto de excel"


def test_extract_docx_is_skipped_when_no_extractor_was_injected():
    extractor = make_extractor(docx_extractor=None)
    result = extractor.extract(
        {"id": "d1", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    )
    assert not result.ok


def test_extract_image_uses_vision_llm_when_available():
    vision = FakeVisionLLM(response="una foto de un gato")
    extractor = make_extractor(drive=FakeDrive(bytes_map={"i1": b"png-bytes"}), vision_llm=vision)
    result = extractor.extract({"id": "i1", "mimeType": "image/png"})
    assert result.text == "una foto de un gato"
    assert len(vision.calls) == 1


def test_extract_image_uses_the_injected_vision_system_prompt_provider():
    vision = FakeVisionLLM()
    extractor = make_extractor(
        drive=FakeDrive(bytes_map={"i1": b"png-bytes"}),
        vision_llm=vision,
        vision_system_prompt_provider=lambda: "prompt de visión editado",
    )
    extractor.extract({"id": "i1", "mimeType": "image/png"})

    sent_system, _ = vision.calls[0]
    assert sent_system == "prompt de visión editado"


def test_extract_image_is_skipped_when_vision_unavailable():
    extractor = make_extractor(vision_llm=FakeVisionLLM(available=False))
    result = extractor.extract({"id": "i1", "mimeType": "image/png"})
    assert not result.ok
    assert "ANTHROPIC_API_KEY" in result.skipped_reason


def test_extract_audio_uses_stt():
    extractor = make_extractor(drive=FakeDrive(bytes_map={"a1": b"audio-bytes"}), stt=FakeStt(text="lo que se dijo"))
    result = extractor.extract({"id": "a1", "mimeType": "audio/mpeg"})
    assert result.text == "lo que se dijo"


def test_extract_audio_is_skipped_when_stt_unavailable():
    extractor = make_extractor(stt=FakeStt(available=False))
    result = extractor.extract({"id": "a1", "mimeType": "audio/mpeg"})
    assert not result.ok
    assert "ELEVENLABS_API_KEY" in result.skipped_reason


def test_extract_video_extracts_audio_track_then_transcribes():
    extractor = make_extractor(
        drive=FakeDrive(bytes_map={"v1": b"video-bytes"}),
        ffmpeg_audio=FakeFfmpeg(audio_bytes=b"pista-de-audio"),
        stt=FakeStt(text="transcripción del video"),
    )
    result = extractor.extract({"id": "v1", "mimeType": "video/mp4"})
    assert result.text == "transcripción del video"


def test_extract_video_is_skipped_when_ffmpeg_unavailable():
    extractor = make_extractor(ffmpeg_audio=FakeFfmpeg(available=False))
    result = extractor.extract({"id": "v1", "mimeType": "video/mp4"})
    assert not result.ok
    assert "ffmpeg" in result.skipped_reason


def test_extract_unsupported_mime_is_skipped_with_reason():
    extractor = make_extractor()
    result = extractor.extract({"id": "z1", "mimeType": "application/zip"})
    assert not result.ok
    assert "no soportado" in result.skipped_reason


def test_extract_catches_exceptions_and_reports_them_as_error():
    class BoomPdf:
        def extract_text(self, pdf_bytes):
            raise RuntimeError("pdf corrupto")

    extractor = make_extractor(drive=FakeDrive(bytes_map={"p1": b"bytes"}), pdf_extractor=BoomPdf())
    result = extractor.extract({"id": "p1", "mimeType": "application/pdf"})
    assert not result.ok
    assert "pdf corrupto" in result.skipped_reason
