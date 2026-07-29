from snarf.runtime import data_backup


def test_backup_now_copies_files_and_directories(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "usage_log.jsonl").write_text("real-entry-1\nreal-entry-2\n")
    (data_dir / "dashboard_prefs").mkdir()
    (data_dir / "dashboard_prefs" / "fundador.json").write_text('{"a": 1}')

    backup_dir = tmp_path / "data_backups"
    snapshot = data_backup.backup_now(data_dir=data_dir, backup_dir=backup_dir)

    assert (snapshot / "usage_log.jsonl").read_text() == "real-entry-1\nreal-entry-2\n"
    assert (snapshot / "dashboard_prefs" / "fundador.json").read_text() == '{"a": 1}'


def test_backup_now_skips_targets_that_do_not_exist_yet(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    backup_dir = tmp_path / "data_backups"
    snapshot = data_backup.backup_now(data_dir=data_dir, backup_dir=backup_dir)
    assert snapshot.exists()
    assert not (snapshot / "usage_log.jsonl").exists()


def test_backup_now_prunes_older_snapshots_beyond_keep_last_n(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "usage_log.jsonl").write_text("x")
    backup_dir = tmp_path / "data_backups"

    for i in range(5):
        data_backup.backup_now(data_dir=data_dir, backup_dir=backup_dir, keep_last_n=2, stamp=f"snap-{i}")

    remaining = data_backup.list_backups(backup_dir)
    assert len(remaining) == 2


def test_restore_latest_brings_back_the_most_recent_snapshot(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    backup_dir = tmp_path / "data_backups"

    (data_dir / "usage_log.jsonl").write_text("original-real-data\n")
    data_backup.backup_now(data_dir=data_dir, backup_dir=backup_dir)

    # Simula el desastre: el archivo real se corrompe/vacía por error.
    (data_dir / "usage_log.jsonl").write_text("")
    assert (data_dir / "usage_log.jsonl").read_text() == ""

    restored_from = data_backup.restore_latest(data_dir=data_dir, backup_dir=backup_dir)
    assert restored_from is not None
    assert (data_dir / "usage_log.jsonl").read_text() == "original-real-data\n"


def test_restore_latest_with_no_backups_returns_none(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    backup_dir = tmp_path / "data_backups"
    assert data_backup.restore_latest(data_dir=data_dir, backup_dir=backup_dir) is None


def test_list_backups_with_no_backup_dir_is_empty(tmp_path):
    assert data_backup.list_backups(tmp_path / "does_not_exist") == []
