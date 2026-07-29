from snarf.telemetry import pricing, usage_tracker


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
    usage_tracker.record_anthropic_call("claude-haiku-4-5", 1000, 500, path=path)
    entries = usage_tracker._read_all(path)
    assert len(entries) == 1
    assert entries[0]["vendor"] == "anthropic"
    assert entries[0]["model"] == "claude-haiku-4-5"
    assert entries[0]["cost_usd"] > 0


def test_record_elevenlabs_stt_call_without_duration_has_no_cost_estimate(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_elevenlabs_stt_call(None, path=path)
    entries = usage_tracker._read_all(path)
    assert entries[0]["cost_usd"] is None


def test_record_elevenlabs_tts_call_tracks_characters_without_a_dollar_estimate(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_elevenlabs_tts_call(120, path=path)
    entries = usage_tracker._read_all(path)
    assert entries[0]["characters"] == 120
    assert entries[0]["cost_usd"] is None


def test_record_voyage_call_accounts_for_cumulative_free_tokens_already_used(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_voyage_call("voyage-4-lite", pricing.VOYAGE_FREE_TOKENS_PER_ACCOUNT, path=path)
    usage_tracker.record_voyage_call("voyage-4-lite", 1_000_000, path=path)
    entries = usage_tracker._read_all(path)
    assert entries[0]["cost_usd"] == 0.0
    assert entries[1]["cost_usd"] == (1_000_000 / 1_000_000) * pricing.VOYAGE_RATES_PER_MILLION_TOKENS["voyage-4-lite"]


def test_summarize_reports_totals_by_vendor_and_flags_unknown_cost_calls(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_anthropic_call("claude-sonnet-5", 1_000_000, 0, path=path)
    usage_tracker.record_elevenlabs_tts_call(50, path=path)
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
    for i in range(5):
        usage_tracker.record_voyage_call("voyage-4-lite", tokens=i, path=path)
    entries = usage_tracker.recent(n=2, path=path)
    assert [e["tokens"] for e in entries] == [3, 4]


def test_recent_with_no_entries_is_empty(tmp_path):
    path = tmp_path / "no_existe.jsonl"
    assert usage_tracker.recent(path=path) == []


def test_usage_metrics_aggregates_real_consumption_per_vendor(tmp_path):
    path = tmp_path / "usage.jsonl"
    usage_tracker.record_anthropic_call("claude-sonnet-5", 1000, 500, path=path)
    usage_tracker.record_anthropic_call("claude-sonnet-5", 200, 100, path=path)
    usage_tracker.record_elevenlabs_tts_call(120, path=path)
    usage_tracker.record_elevenlabs_stt_call(30.0, path=path)
    usage_tracker.record_voyage_call("voyage-4-lite", 5000, path=path)
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
