from snarf.knowledge.manifest import STATUS_ERROR, STATUS_INDEXED, IndexManifest


def test_needs_processing_is_true_for_a_file_never_seen_before(tmp_path):
    manifest = IndexManifest(tmp_path / "manifest.json")
    assert manifest.needs_processing({}, "f1", "2026-01-01T00:00:00Z") is True


def test_needs_processing_is_false_once_indexed_with_the_same_modified_time(tmp_path):
    manifest = IndexManifest(tmp_path / "manifest.json")
    data = {}
    manifest.mark(data, "f1", "2026-01-01T00:00:00Z", STATUS_INDEXED, chunk_count=3)
    assert manifest.needs_processing(data, "f1", "2026-01-01T00:00:00Z") is False


def test_needs_processing_is_true_again_when_modified_time_changed(tmp_path):
    manifest = IndexManifest(tmp_path / "manifest.json")
    data = {}
    manifest.mark(data, "f1", "2026-01-01T00:00:00Z", STATUS_INDEXED)
    assert manifest.needs_processing(data, "f1", "2026-02-01T00:00:00Z") is True


def test_needs_processing_is_true_for_a_file_previously_marked_as_error(tmp_path):
    # Un error (ej. credencial faltante, falla transitoria) no es un resultado
    # estable: debe reintentarse en la próxima corrida aunque el archivo no
    # haya cambiado, a diferencia de "indexed" o "skipped_unsupported".
    manifest = IndexManifest(tmp_path / "manifest.json")
    data = {}
    manifest.mark(data, "f1", "2026-01-01T00:00:00Z", STATUS_ERROR, reason="VOYAGE_API_KEY no configurada")
    assert manifest.needs_processing(data, "f1", "2026-01-01T00:00:00Z") is True


def test_save_and_load_roundtrip_preserves_entries(tmp_path):
    path = tmp_path / "manifest.json"
    data = {}
    IndexManifest(path).mark(data, "f1", "t1", STATUS_INDEXED, chunk_count=5)
    IndexManifest(path).save(data)

    reloaded = IndexManifest(path).load()
    assert reloaded["f1"]["chunk_count"] == 5
    assert reloaded["f1"]["modifiedTime"] == "t1"


def test_load_returns_empty_dict_when_no_file_exists_yet(tmp_path):
    assert IndexManifest(tmp_path / "no_existe.json").load() == {}


def test_save_leaves_no_temp_file_behind_and_survives_repeated_writes(tmp_path):
    """Bug real visto en producción: mientras una indexación corre en
    background guardando seguido, el dashboard lee el mismo archivo en
    paralelo (polling) — con la escritura vieja (write_text, no atómica),
    un lector podía atrapar el archivo a mitad de escritura y recibir un
    JSON truncado (json.JSONDecodeError real). save() ahora escribe a un
    temporal y renombra (os.replace, atómico) — un lector siempre ve el
    archivo viejo completo o el nuevo completo, nunca una mezcla; y no debe
    quedar ningún .tmp huérfano tras un save exitoso."""
    path = tmp_path / "manifest.json"
    manifest = IndexManifest(path)
    data = {}
    for i in range(20):
        manifest.mark(data, f"f{i}", f"t{i}", STATUS_INDEXED, chunk_count=i)
        manifest.save(data)

    reloaded = IndexManifest(path).load()
    assert len(reloaded) == 20
    assert reloaded["f19"]["modifiedTime"] == "t19"
    assert list(tmp_path.glob("*.tmp")) == []
