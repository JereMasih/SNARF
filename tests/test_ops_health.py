from pathlib import Path

from snarf.runtime.ops_health import system_health

_NONEXISTENT = Path("/definitely/does/not/exist")


def test_reports_llm_and_google_availability_directly():
    result = system_health(llm_available=True, google_available=False, recent_activity=[], data_dir=_NONEXISTENT)
    assert result["llm_available"] is True
    assert result["google_available"] is False


def test_counts_recent_calls_and_errors_separately():
    activity = [
        {"status": "ok"},
        {"status": "error"},
        {"status": "ok"},
        {"status": "error"},
    ]
    result = system_health(True, True, activity, data_dir=_NONEXISTENT)
    assert result["recent_call_count"] == 4
    assert result["recent_error_count"] == 2


def test_reports_zero_disk_usage_for_a_nonexistent_directory():
    result = system_health(True, True, [], data_dir=_NONEXISTENT)
    assert result["data_dir_size_mb"] == 0.0


def test_reports_real_disk_usage_for_an_existing_directory(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 1024 * 1024)  # 1 MB real
    result = system_health(True, True, [], data_dir=tmp_path)
    assert result["data_dir_size_mb"] == 1.0


# --- Fase 2 del plan de observabilidad: dispatcher/redis stats reales -----


def test_includes_real_event_dispatcher_stats():
    result = system_health(True, True, [], data_dir=_NONEXISTENT)
    assert set(result["event_dispatcher"].keys()) == {"published", "dropped", "by_subscriber"}


def test_includes_redis_health_reported_as_not_configured_by_default():
    result = system_health(True, True, [], data_dir=_NONEXISTENT)
    assert result["event_bus_redis"]["configured"] is False


def test_includes_n8n_health_reported_as_not_configured_by_default():
    result = system_health(True, True, [], data_dir=_NONEXISTENT)
    assert result["event_bus_n8n"]["configured"] is False
