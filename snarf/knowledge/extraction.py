import base64

GOOGLE_NATIVE_TEXT_MIME = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

VIDEO_EXTENSION_BY_MIME = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}

VISION_SYSTEM_PROMPT = "Extraés y describís contenido de imágenes para indexarlo como texto buscable."
VISION_PROMPT = (
    "Describí el contenido de esta imagen en español, de forma breve y concreta. "
    "Si contiene texto legible (un documento escaneado, un cartel, una captura de "
    "pantalla), transcribilo tal cual. Si es una foto sin texto, describí qué se ve."
)


def categorize_mime(mime: str) -> str:
    if mime == "application/vnd.google-apps.folder":
        return "folder"
    if mime in GOOGLE_NATIVE_TEXT_MIME:
        return "google_doc"
    if mime == PDF_MIME:
        return "pdf"
    if mime == DOCX_MIME:
        return "docx"
    if mime == PPTX_MIME:
        return "pptx"
    if mime == XLSX_MIME:
        return "xlsx"
    if mime.startswith("text/"):
        return "text"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "other"


class ExtractionResult:
    def __init__(self, text: str | None = None, skipped_reason: str | None = None):
        self.text = text
        self.skipped_reason = skipped_reason

    @property
    def ok(self) -> bool:
        return self.text is not None


class ContentExtractor:
    """Capacidad de orquestación: dado un archivo de Drive (id + mimeType),
    devuelve su contenido como texto, delegando en la Capacidad correcta
    según el tipo. Recibe todo por inyección — sin importar snarf.core ni
    snarf.runtime (ver ADR 0026 y tests/test_architecture_boundaries.py)."""

    def __init__(self, drive, pdf_extractor, vision_llm, stt, ffmpeg_audio, docx_extractor=None, pptx_extractor=None, xlsx_extractor=None):
        self._drive = drive
        self._pdf = pdf_extractor
        self._vision_llm = vision_llm
        self._stt = stt
        self._ffmpeg = ffmpeg_audio
        self._docx = docx_extractor
        self._pptx = pptx_extractor
        self._xlsx = xlsx_extractor
        self._binary_extractors = {PDF_MIME: self._pdf, DOCX_MIME: self._docx, PPTX_MIME: self._pptx, XLSX_MIME: self._xlsx}

    def extract(self, file: dict) -> ExtractionResult:
        mime = file.get("mimeType", "") or ""
        file_id = file["id"]
        try:
            if mime in GOOGLE_NATIVE_TEXT_MIME or mime.startswith("text/"):
                return ExtractionResult(self._drive.read_file_text(file_id, mime))
            extractor = self._binary_extractors.get(mime)
            if extractor is not None:
                return ExtractionResult(extractor.extract_text(self._drive.read_file_bytes(file_id)))
            if mime.startswith("image/"):
                return self._extract_image(file_id, mime)
            if mime.startswith("audio/"):
                return self._extract_audio(file_id)
            if mime.startswith("video/"):
                return self._extract_video(file_id, mime)
        except Exception as exc:
            return ExtractionResult(skipped_reason=f"error: {exc}")
        return ExtractionResult(skipped_reason=f"tipo no soportado: {mime}")

    def _extract_image(self, file_id: str, mime: str) -> ExtractionResult:
        if not self._vision_llm.available:
            return ExtractionResult(skipped_reason="visión no disponible (falta ANTHROPIC_API_KEY)")
        image_bytes = self._drive.read_file_bytes(file_id)
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(image_bytes).decode("ascii")},
            },
            {"type": "text", "text": VISION_PROMPT},
        ]
        text = self._vision_llm.generate(system=VISION_SYSTEM_PROMPT, messages=[{"role": "user", "content": content}])
        return ExtractionResult(text)

    def _extract_audio(self, file_id: str) -> ExtractionResult:
        if not self._stt.available:
            return ExtractionResult(skipped_reason="transcripción no disponible (falta ELEVENLABS_API_KEY)")
        audio_bytes = self._drive.read_file_bytes(file_id)
        return ExtractionResult(self._stt.transcribe(audio_bytes))

    def _extract_video(self, file_id: str, mime: str) -> ExtractionResult:
        if not self._ffmpeg.available:
            return ExtractionResult(skipped_reason="ffmpeg no está instalado en el sistema")
        if not self._stt.available:
            return ExtractionResult(skipped_reason="transcripción no disponible (falta ELEVENLABS_API_KEY)")
        video_bytes = self._drive.read_file_bytes(file_id)
        suffix = VIDEO_EXTENSION_BY_MIME.get(mime, ".mp4")
        audio_bytes = self._ffmpeg.extract_audio(video_bytes, suffix=suffix)
        return ExtractionResult(self._stt.transcribe(audio_bytes))
