from snarf.capabilities.google_drive import normalize_drive_query


def test_plain_free_text_gets_wrapped_as_full_text_search():
    assert normalize_drive_query("Tommy") == "fullText contains 'Tommy'"


def test_free_text_with_spaces_and_accents_gets_wrapped():
    assert normalize_drive_query("vida es sueño") == "fullText contains 'vida es sueño'"


def test_free_text_with_double_quotes_and_or_still_gets_wrapped():
    # Caso real que rompía la API: intento de OR mal formado, texto libre
    # con comillas dobles — se trata como un único literal de texto
    # completo, nunca como una query estructurada rota. Las comillas
    # dobles no son el delimitador real de Drive (comilla simple), así que
    # no necesitan escape.
    query = 'análisis "vida es sueño" OR "La vida es sueño" análisis'
    result = normalize_drive_query(query)
    assert result == f"fullText contains '{query}'"


def test_free_text_with_single_quotes_gets_escaped():
    query = "no es 'la' respuesta"
    result = normalize_drive_query(query)
    assert result == "fullText contains 'no es \\'la\\' respuesta'"


def test_real_drive_syntax_with_equals_passes_through_unchanged():
    query = "name = 'Snarf - Archivos' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    assert normalize_drive_query(query) == query


def test_real_drive_syntax_with_in_parents_passes_through_unchanged():
    query = "'folder-id-123' in parents"
    assert normalize_drive_query(query) == query


def test_real_drive_syntax_with_contains_passes_through_unchanged():
    query = "fullText contains 'informe'"
    assert normalize_drive_query(query) == query


def test_word_boundary_never_false_positives_on_in_inside_another_word():
    # "Argentina"/"indexado" contienen "in" como substring, nunca como
    # palabra real — no deben confundirse con el operador real `in`.
    assert normalize_drive_query("Argentina indexado") == "fullText contains 'Argentina indexado'"


def test_backslash_in_free_text_is_escaped():
    result = normalize_drive_query("ruta\\archivo")
    assert result == "fullText contains 'ruta\\\\archivo'"
