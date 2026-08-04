from snarf.telemetry import context


def test_get_conversation_id_is_none_by_default():
    context.clear_conversation_id()
    assert context.get_conversation_id() is None


def test_set_and_get_conversation_id_roundtrip():
    context.set_conversation_id("conv-123")
    assert context.get_conversation_id() == "conv-123"
    context.clear_conversation_id()
    assert context.get_conversation_id() is None
