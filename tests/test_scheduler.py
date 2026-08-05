from datetime import datetime
from zoneinfo import ZoneInfo

from snarf.runtime.scheduler import next_run_at


def test_returns_today_when_the_clock_time_has_not_passed_yet():
    now = datetime(2026, 8, 5, 7, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    result = next_run_at(8, 0, "America/Argentina/Buenos_Aires", now=now)
    expected = datetime(2026, 8, 5, 8, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")).timestamp()
    assert result == expected


def test_rolls_over_to_tomorrow_when_the_clock_time_already_passed():
    now = datetime(2026, 8, 5, 9, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    result = next_run_at(8, 0, "America/Argentina/Buenos_Aires", now=now)
    expected = datetime(2026, 8, 6, 8, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")).timestamp()
    assert result == expected


def test_exact_clock_time_rolls_over_to_tomorrow_not_today():
    now = datetime(2026, 8, 5, 8, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    result = next_run_at(8, 0, "America/Argentina/Buenos_Aires", now=now)
    expected = datetime(2026, 8, 6, 8, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")).timestamp()
    assert result == expected


def test_respects_the_given_timezone_not_the_system_one():
    now_utc = datetime(2026, 8, 5, 10, 0, tzinfo=ZoneInfo("UTC"))
    result = next_run_at(8, 0, "America/Argentina/Buenos_Aires", now=now_utc)
    # 10:00 UTC = 07:00 en Buenos Aires (UTC-3) — todavía no pasaron las 8, así que es hoy.
    expected = datetime(2026, 8, 5, 8, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")).timestamp()
    assert result == expected
