from snarf.core.orchestrator import TOOLS
from snarf.telemetry import detail


def test_detail_extractors_cover_every_orchestrator_tool():
    # Regresión: si se agrega una herramienta nueva al Orchestrator y se
    # olvida agregar su extractor de detalle, este test la detecta en vez de
    # dejarla invisible en silencio en el dock HUD (mismo criterio que
    # test_tool_to_node_covers_every_orchestrator_tool en tests/test_brain.py).
    real_tool_names = {tool["name"] for tool in TOOLS}
    assert set(detail.DETAIL_EXTRACTORS.keys()) == real_tool_names


def test_extract_returns_none_for_unmapped_tool():
    assert detail.extract("tool_que_no_existe", "ok", {}, {}) is None


def test_extract_unknown_tool_uses_the_real_attempted_name():
    result = detail.extract("un_tool_inventado_por_el_modelo", "unknown_tool", {}, None)
    assert result == "intentando “un_tool_inventado_por_el_modelo”"


def test_every_extractor_survives_empty_input_and_result():
    # Ningún extractor debe romper el dispatch real de un tool por un
    # detalle decorativo — ante tool_input/result vacíos o con forma
    # inesperada, siempre str o None, nunca una excepción (un resultado
    # vacío puede ser contenido real y válido, ej. "0 caracteres").
    for tool_name in detail.DETAIL_EXTRACTORS:
        for fake_input, fake_result in (({}, None), ({}, {}), ({}, []), (None, None)):
            result = detail.extract(tool_name, "ok", fake_input, fake_result)
            assert result is None or isinstance(result, str)


def test_gmail_send_message_detail_has_real_recipient_and_subject():
    result = detail.extract(
        "gmail_send_message", "ok", {"to": "tommy@example.com", "subject": "El plan del canal", "body": "..."}, {"status": "sent"}
    )
    assert result == "para tommy@example.com: “El plan del canal”"


def test_search_memory_detail_has_real_query():
    result = detail.extract("search_memory", "ok", {"query": "canal de Tommy"}, [])
    assert result == "buscando: “canal de Tommy”"


def test_drive_create_document_detail_has_real_title():
    result = detail.extract(
        "drive_create_document", "ok", {"title": "Plan del canal", "content": "..."}, {"status": "created"}
    )
    assert result == "redactando “Plan del canal”"


def test_drive_list_files_detail_counts_real_results():
    files = [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]
    result = detail.extract("drive_list_files", "ok", {}, files)
    assert result == "2 archivos"


def test_drive_list_files_detail_includes_real_query_when_present():
    files = [{"id": "1", "name": "a"}]
    result = detail.extract("drive_list_files", "ok", {"query": "reportes"}, files)
    assert result == "1 archivos para “reportes”"


def test_drive_list_files_pending_confirmation_never_invents_content():
    pending = {"status": "pending_confirmation", "preview": {"page_size": 500}, "instructions": "..."}
    result = detail.extract("drive_list_files", "ok", {}, pending)
    assert result == "pendiente de confirmación (pedido grande)"


def test_get_conversation_detail_uses_real_first_message():
    result = detail.extract(
        "get_conversation", "ok", {"conversation_id": "abc"}, [{"input": "¿en qué quedó esto?", "response": "..."}]
    )
    assert result == "revisando: “¿en qué quedó esto?”"


def test_gmail_summarize_inbox_detail_uses_real_message_count():
    result = detail.extract(
        "gmail_summarize_inbox", "ok", {}, {"message_count": 7, "digest_text": "...", "messages": []}
    )
    assert result == "curando 7 correos"


def test_morning_routine_detail_uses_real_counts():
    result = detail.extract(
        "morning_routine",
        "ok",
        {},
        {"message_count": 5, "event_count": 2, "priority_message_ids": ["m1", "m2"], "routine_text": "..."},
    )
    assert result == "rutina: 5 correos, 2 eventos, 2 prioritarios leídos"


def test_drive_move_file_detail_falls_back_to_short_id_when_no_name_available():
    # drive_move_file solo recibe IDs en su input real — no hay nombre
    # legible disponible, el detalle es honestamente genérico en vez de
    # inventar un nombre de archivo.
    result = detail.extract("drive_move_file", "ok", {"file_id": "1a2b3c4d5e6f7g8h", "new_parent_id": "x"}, {})
    assert result is not None
    assert "1a2b3c4d5e" in result


def test_truncate_detalle_returns_none_for_empty_text():
    assert detail.truncate_detalle("") is None
    assert detail.truncate_detalle(None) is None


def test_truncate_detalle_caps_at_max_chars():
    long_text = "x" * 500
    result = detail.truncate_detalle(long_text)
    assert result is not None
    assert len(result) <= detail.DETAIL_MAX_CHARS


def test_extract_never_raises_on_malformed_result_shape():
    # Ej. gmail_read_message espera un dict con "subject" — pasarle una
    # lista no debe romper nada.
    assert detail.extract("gmail_read_message", "ok", {"message_id": "1"}, ["no", "es", "un", "dict"]) is None


# --- extract_preview (ADR 0092) --------------------------------------------


def test_preview_extractors_only_reference_real_tools():
    # A diferencia de DETAIL_EXTRACTORS, PREVIEW_EXTRACTORS es a propósito
    # parcial (la mayoría de los tools no toca ningún documento real) — pero
    # cualquier key tiene que seguir siendo un tool real del Orchestrator,
    # nunca un nombre que ya no existe.
    real_tool_names = {tool["name"] for tool in TOOLS}
    assert set(detail.PREVIEW_EXTRACTORS.keys()) <= real_tool_names


def test_extract_preview_returns_none_for_tool_without_document():
    assert detail.extract_preview("search_memory", {"query": "x"}, []) is None


def test_extract_preview_returns_none_when_tool_call_failed():
    assert detail.extract_preview("drive_read_file", {"file_id": "f1", "mime_type": "application/pdf"}, {"error": "no se pudo"}) is None


def test_every_preview_extractor_survives_empty_input_and_result():
    for tool_name in detail.PREVIEW_EXTRACTORS:
        for fake_input, fake_result in (({}, None), ({}, {}), ({}, []), (None, None)):
            result = detail.extract_preview(tool_name, fake_input, fake_result)
            assert result is None or isinstance(result, dict)


def test_drive_read_file_preview_has_real_snippet_and_google_doc_link():
    result = detail.extract_preview(
        "drive_read_file",
        {"file_id": "abc123", "mime_type": "application/vnd.google-apps.document"},
        "Plan de contenido — Canal de edits de fútbol de Tommy...",
    )
    assert result["title"] is None  # el nombre real del archivo no viaja en tool_input/result — nunca se inventa
    assert result["link"] == "https://docs.google.com/document/d/abc123/edit"
    assert result["snippet"] == "Plan de contenido — Canal de edits de fútbol de Tommy..."


def test_drive_read_file_preview_falls_back_to_generic_drive_link_for_non_google_mime():
    result = detail.extract_preview("drive_read_file", {"file_id": "abc123", "mime_type": "application/pdf"}, "texto del pdf")
    assert result["link"] == "https://drive.google.com/file/d/abc123/view"


def test_drive_create_document_preview_has_real_title_and_link():
    result = detail.extract_preview(
        "drive_create_document",
        {"title": "Plan del canal", "content": "..."},
        {"id": "xyz", "name": "Plan del canal", "webViewLink": "https://docs.google.com/document/d/xyz/edit", "indexed": True, "location": "drive"},
    )
    assert result == {"title": "Plan del canal", "link": "https://docs.google.com/document/d/xyz/edit", "snippet": None}


def test_drive_create_document_preview_uses_download_url_when_local_destination():
    result = detail.extract_preview(
        "drive_create_document",
        {"title": "Nota local", "content": "...", "destination": "device"},
        {"id": "local:1", "name": "Nota local.md", "path": "/x", "webViewLink": None, "indexed": True, "location": "device", "download_url": "/files/local/u1/Nota local.md"},
    )
    assert result["link"] == "/files/local/u1/Nota local.md"


def test_notion_create_page_preview_has_real_title_and_url():
    result = detail.extract_preview(
        "notion_create_page", {"parent_page_id": "p1", "title": "Resumen semanal"}, {"id": "page1", "url": "https://www.notion.so/page1"}
    )
    assert result == {"title": "Resumen semanal", "link": "https://www.notion.so/page1", "snippet": None}


def test_notion_read_page_preview_has_real_snippet_and_constructed_link():
    result = detail.extract_preview("notion_read_page", {"page_id": "abc-123-def"}, "contenido real de la página")
    assert result["link"] == "https://www.notion.so/abc123def"
    assert result["snippet"] == "contenido real de la página"


def test_drive_update_document_preview_has_link_only_on_confirmed_update():
    result = detail.extract_preview(
        "drive_update_document", {"file_id": "doc1", "new_content": "..."}, {"documentId": "doc1", "status": "updated"}
    )
    assert result == {"title": None, "link": "https://docs.google.com/document/d/doc1/edit", "snippet": None}


def test_drive_update_document_preview_is_none_while_pending_confirmation():
    pending = {"status": "pending_confirmation", "preview": {}, "instructions": "..."}
    assert detail.extract_preview("drive_update_document", {"file_id": "doc1", "new_content": "..."}, pending) is None
