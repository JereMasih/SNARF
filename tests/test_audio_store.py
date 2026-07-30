import time

from snarf.memory.audio_store import AudioStore


def make_store(tmp_path):
    return AudioStore(directory=tmp_path / "audio")


def test_save_and_path_for_roundtrip(tmp_path):
    store = make_store(tmp_path)
    audio_id = store.save(b"fake audio bytes", "webm")
    assert audio_id.endswith(".webm")
    path = store.path_for(audio_id)
    assert path is not None
    assert path.read_bytes() == b"fake audio bytes"


def test_save_falls_back_to_webm_for_an_unknown_extension(tmp_path):
    store = make_store(tmp_path)
    audio_id = store.save(b"data", "exe")
    assert audio_id.endswith(".webm")


def test_path_for_rejects_path_traversal_attempts(tmp_path):
    store = make_store(tmp_path)
    assert store.path_for("../../etc/passwd") is None
    assert store.path_for("..%2f..%2fetc%2fpasswd.mp3") is None
    assert store.path_for("foo/bar.mp3") is None


def test_path_for_rejects_an_invalid_extension(tmp_path):
    store = make_store(tmp_path)
    (store.directory / "evil.py").write_bytes(b"import os")
    assert store.path_for("evil.py") is None


def test_path_for_returns_none_for_a_missing_file(tmp_path):
    store = make_store(tmp_path)
    assert store.path_for("00000000000000000000000000000000.mp3") is None


def test_tts_cache_roundtrip_same_text_same_id(tmp_path):
    store = make_store(tmp_path)
    assert store.get_cached_tts("hola") is None
    audio_id = store.save_tts("hola", b"synth bytes")
    assert store.get_cached_tts("hola") == b"synth bytes"
    # mismo texto -> mismo id de caché, para no sintetizar dos veces lo mismo
    assert store.save_tts("hola", b"synth bytes") == audio_id


def test_purge_older_than_deletes_only_expired_files(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    old_id = store.save(b"old", "webm")
    new_id = store.save(b"new", "webm")
    old_path = store.path_for(old_id)
    old_time = time.time() - 999999
    import os

    os.utime(old_path, (old_time, old_time))

    deleted = store.purge_older_than(max_age_seconds=3600)
    assert deleted == 1
    assert store.path_for(old_id) is None
    assert store.path_for(new_id) is not None
