from snarf.telemetry import events, pricing, usage_tracker


def test_estimate_anthropic_cost_charges_input_and_output_at_model_rate():
    cost = pricing.estimate_anthropic_cost("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 2.0 + 10.0


def test_estimate_anthropic_cost_discounts_cache_reads():
    cost = pricing.estimate_anthropic_cost("claude-sonnet-5", input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
    assert cost == 2.0 * pricing.ANTHROPIC_CACHE_READ_DISCOUNT


def test_estimate_anthropic_cost_falls_back_to_default_rate_for_unknown_model():
    cost = pricing.estimate_anthropic_cost("modelo-inexistente", input_tokens=1_000_000, output_tokens=0)
    assert cost == pricing.DEFAULT_ANTHROPIC_RATE[0]


def test_estimate_stt_cost_is_proportional_to_duration():
    cost = pricing.estimate_stt_cost(3600)
    assert cost == pricing.ELEVENLABS_STT_USD_PER_HOUR


def test_estimate_voyage_cost_is_free_within_account_allowance():
    cost = pricing.estimate_voyage_cost("voyage-4-lite", tokens=1_000_000, cumulative_tokens_before=0)
    assert cost == 0.0


def test_estimate_voyage_cost_charges_only_the_portion_past_the_free_allowance():
    cumulative_before = pricing.VOYAGE_FREE_TOKENS_PER_ACCOUNT - 500_000
    cost = pricing.estimate_voyage_cost("voyage-4-lite", tokens=1_000_000, cumulative_tokens_before=cumulative_before)
    assert cost == (500_000 / 1_000_000) * pricing.VOYAGE_RATES_PER_MILLION_TOKENS["voyage-4-lite"]


def test_record_anthropic_call_persists_estimated_cost(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_anthropic_call("claude-haiku-4-5", 1000, 500, path=path, events_path=tmp_path / "events.jsonl")
    entries = usage_tracker._read_all(path)
    assert len(entries) == 1
    assert entries[0]["vendor"] == "anthropic"
    assert entries[0]["model"] == "claude-haiku-4-5"
    assert entries[0]["cost_usd"] > 0


def test_estimate_generic_llm_cost_uses_the_given_rate():
    cost = pricing.estimate_generic_llm_cost(
        pricing.GEMINI_RATES_PER_MILLION_TOKENS, pricing.DEFAULT_GEMINI_RATE, "gemini-2.5-flash-lite", 1_000_000, 1_000_000
    )
    input_rate, output_rate = pricing.GEMINI_RATES_PER_MILLION_TOKENS["gemini-2.5-flash-lite"]
    assert cost == input_rate + output_rate


def test_estimate_generic_llm_cost_falls_back_to_default_for_an_unknown_model():
    cost = pricing.estimate_generic_llm_cost(pricing.XAI_RATES_PER_MILLION_TOKENS, pricing.DEFAULT_XAI_RATE, "modelo-nuevo-sin-tarifa", 1_000_000, 0)
    assert cost == pricing.DEFAULT_XAI_RATE[0]


def test_record_generic_llm_call_persists_estimated_cost(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_generic_llm_call("gemini", "gemini-2.5-flash-lite", 1000, 500, path=path, events_path=tmp_path / "events.jsonl")
    entries = usage_tracker._read_all(path)
    assert len(entries) == 1
    assert entries[0]["vendor"] == "gemini"
    assert entries[0]["model"] == "gemini-2.5-flash-lite"
    assert entries[0]["cost_usd"] > 0


def test_record_elevenlabs_stt_call_without_duration_has_no_cost_estimate(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_elevenlabs_stt_call(None, path=path, events_path=tmp_path / "events.jsonl")
    entries = usage_tracker._read_all(path)
    assert entries[0]["cost_usd"] is None


def test_record_elevenlabs_tts_call_tracks_characters_without_a_dollar_estimate(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_elevenlabs_tts_call(120, path=path, events_path=tmp_path / "events.jsonl")
    entries = usage_tracker._read_all(path)
    assert entries[0]["characters"] == 120
    assert entries[0]["cost_usd"] is None


def test_record_voyage_call_accounts_for_cumulative_free_tokens_already_used(tmp_path):
    path = tmp_path / "usage.jsonl"
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_voyage_call("voyage-4-lite", pricing.VOYAGE_FREE_TOKENS_PER_ACCOUNT, path=path, events_path=events_path)
    usage_tracker.record_voyage_call("voyage-4-lite", 1_000_000, path=path, events_path=events_path)
    entries = usage_tracker._read_all(path)
    assert entries[0]["cost_usd"] == 0.0
    assert entries[1]["cost_usd"] == (1_000_000 / 1_000_000) * pricing.VOYAGE_RATES_PER_MILLION_TOKENS["voyage-4-lite"]


def test_summarize_reports_totals_by_vendor_and_flags_unknown_cost_calls(tmp_path):
    path = tmp_path / "usage.jsonl"
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_anthropic_call("claude-sonnet-5", 1_000_000, 0, path=path, events_path=events_path)
    usage_tracker.record_elevenlabs_tts_call(50, path=path, events_path=events_path)
    summary = usage_tracker.summarize(path=path)
    assert summary["total_usd"] == 2.0
    assert summary["by_vendor_usd"] == {"anthropic": 2.0}
    assert summary["total_calls"] == 2
    assert summary["calls_without_cost_estimate"] == 1


def test_summarize_with_no_entries_reports_zeroes(tmp_path):
    path = tmp_path / "usage.jsonl"
    summary = usage_tracker.summarize(path=path)
    assert summary["total_usd"] == 0
    assert summary["total_calls"] == 0


def test_recent_returns_only_the_last_n_entries(tmp_path):
    path = tmp_path / "usage.jsonl"
    events_path = tmp_path / "events.jsonl"
    for i in range(5):
        usage_tracker.record_voyage_call("voyage-4-lite", tokens=i, path=path, events_path=events_path)
    entries = usage_tracker.recent(n=2, path=path)
    assert [e["tokens"] for e in entries] == [3, 4]


def test_recent_with_no_entries_is_empty(tmp_path):
    path = tmp_path / "no_existe.jsonl"
    assert usage_tracker.recent(path=path) == []


def test_usage_metrics_aggregates_real_consumption_per_vendor(tmp_path):
    path = tmp_path / "usage.jsonl"
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_anthropic_call("claude-sonnet-5", 1000, 500, path=path, events_path=events_path)
    usage_tracker.record_anthropic_call("claude-sonnet-5", 200, 100, path=path, events_path=events_path)
    usage_tracker.record_elevenlabs_tts_call(120, path=path, events_path=events_path)
    usage_tracker.record_elevenlabs_stt_call(30.0, path=path, events_path=events_path)
    usage_tracker.record_voyage_call("voyage-4-lite", 5000, path=path, events_path=events_path)
    metrics = usage_tracker.usage_metrics(path=path)
    assert metrics["anthropic"]["calls"] == 2
    assert metrics["anthropic"]["input_tokens"] == 1200
    assert metrics["anthropic"]["output_tokens"] == 600
    assert metrics["elevenlabs"]["calls"] == 2
    assert metrics["elevenlabs"]["characters"] == 120
    assert metrics["elevenlabs"]["duration_seconds"] == 30.0
    assert metrics["voyage"]["tokens"] == 5000


def test_usage_metrics_with_no_entries_is_empty(tmp_path):
    path = tmp_path / "no_existe.jsonl"
    assert usage_tracker.usage_metrics(path=path) == {}


def test_record_anthropic_call_marks_the_unified_event_as_truncado_on_max_tokens(tmp_path):
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_anthropic_call(
        "claude-sonnet-5", 1000, 500, path=tmp_path / "usage.jsonl", events_path=events_path, stop_reason="max_tokens"
    )
    emitted = events.recent(path=events_path)
    assert emitted[0]["estado"] == "truncado"


def test_record_anthropic_call_marks_the_unified_event_as_completo_without_max_tokens(tmp_path):
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_anthropic_call(
        "claude-sonnet-5", 1000, 500, path=tmp_path / "usage.jsonl", events_path=events_path, stop_reason="end_turn"
    )
    emitted = events.recent(path=events_path)
    assert emitted[0]["estado"] == "completo"


def test_record_generic_llm_call_emits_a_unified_event_on_the_llm_node(tmp_path):
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_generic_llm_call("xai", "grok-4.1-fast", 1000, 500, path=tmp_path / "usage.jsonl", events_path=events_path)
    emitted = events.recent(path=events_path)
    assert emitted[0]["nodo"] == "llm"
    assert emitted[0]["modelo"] == "grok-4.1-fast"
    assert emitted[0]["tokens_in"] == 1000
    assert emitted[0]["tokens_out"] == 500


def test_record_anthropic_call_threads_duration_ms_into_the_unified_event(tmp_path):
    # "Tiempos, data útil" al hacer click en el feed del cerebro (pedido
    # explícito) — antes latencia_ms quedaba siempre None para llamadas de
    # LLM, el campo existía en el schema pero nunca se llenaba acá.
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_anthropic_call(
        "claude-sonnet-5", 1000, 500, path=tmp_path / "usage.jsonl", events_path=events_path, duration_ms=1234.5
    )
    emitted = events.recent(path=events_path)
    assert emitted[0]["latencia_ms"] == 1234.5


def test_record_generic_llm_call_threads_duration_ms_into_the_unified_event(tmp_path):
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_generic_llm_call(
        "xai", "grok-4.1-fast", 1000, 500, path=tmp_path / "usage.jsonl", events_path=events_path, duration_ms=567.0
    )
    emitted = events.recent(path=events_path)
    assert emitted[0]["latencia_ms"] == 567.0


def test_record_groq_stt_call_emits_a_unified_event_on_the_stt_node(tmp_path):
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_groq_stt_call(12.5, path=tmp_path / "usage.jsonl", events_path=events_path)
    emitted = events.recent(path=events_path)
    assert emitted[0]["nodo"] == "stt"


def test_record_local_stt_and_tts_calls_split_by_model_into_stt_and_tts_nodes(tmp_path):
    events_path = tmp_path / "events.jsonl"
    usage_tracker.record_local_stt_call(4.0, path=tmp_path / "usage.jsonl", events_path=events_path)
    usage_tracker.record_kokoro_tts_call(80, path=tmp_path / "usage.jsonl", events_path=events_path)
    emitted = events.recent(path=events_path)
    assert emitted[0]["nodo"] == "stt"
    assert emitted[1]["nodo"] == "tts"
