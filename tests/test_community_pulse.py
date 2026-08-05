from snarf.specialists.community.pulse import CommunityPulseSpecialist


class FakeDiscord:
    def __init__(self, available=True, messages=None, member_count=0):
        self.available = available
        self._messages = messages or []
        self._member_count = member_count

    def list_recent_messages(self, limit=50):
        return self._messages[:limit]

    def guild_member_count(self):
        return self._member_count


def test_pulse_reports_an_error_when_discord_is_not_configured():
    specialist = CommunityPulseSpecialist(FakeDiscord(available=False))
    result = specialist.pulse()
    assert "error" in result
    assert "Discord no está configurado" in result["error"]


def test_pulse_computes_real_metrics_from_recent_messages():
    messages = [
        {"author": "jere", "content": "hola"},
        {"author": "jere", "content": "otro mensaje"},
        {"author": "ana", "content": "hey"},
    ]
    specialist = CommunityPulseSpecialist(FakeDiscord(messages=messages, member_count=50))
    result = specialist.pulse()
    assert result == {"member_count": 50, "recent_message_count": 3, "active_author_count": 2}


def test_pulse_respects_message_limit():
    messages = [{"author": f"u{i}", "content": "x"} for i in range(10)]
    specialist = CommunityPulseSpecialist(FakeDiscord(messages=messages, member_count=1))
    result = specialist.pulse(message_limit=3)
    assert result["recent_message_count"] == 3


def test_handle_returns_a_readable_summary():
    specialist = CommunityPulseSpecialist(FakeDiscord(messages=[{"author": "a", "content": "x"}], member_count=5))
    text = specialist.handle("pulse", {})
    assert "5 miembros" in text


def test_handle_returns_the_error_when_not_configured():
    specialist = CommunityPulseSpecialist(FakeDiscord(available=False))
    assert "no está configurado" in specialist.handle("pulse", {})
