import json
import time
from pathlib import Path

from snarf.telemetry import pricing

DEFAULT_PATH = Path("data/usage_log.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def record(vendor: str, model: str, cost_usd: float | None, metric: dict, path: Path | None = None) -> None:
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": time.time(), "vendor": vendor, "model": model, "cost_usd": cost_usd, **metric}
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_anthropic_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    path: Path | None = None,
) -> None:
    cost = pricing.estimate_anthropic_cost(model, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens)
    record(
        "anthropic",
        model,
        cost,
        {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_tokens": cache_creation_tokens,
            "cache_read_tokens": cache_read_tokens,
        },
        path=path,
    )


def record_elevenlabs_stt_call(duration_seconds: float | None, path: Path | None = None) -> None:
    cost = pricing.estimate_stt_cost(duration_seconds) if duration_seconds is not None else None
    record("elevenlabs", "stt_scribe", cost, {"duration_seconds": duration_seconds}, path=path)


def record_elevenlabs_tts_call(characters: int, path: Path | None = None) -> None:
    # ElevenLabs TTS suele facturarse contra un cupo de caracteres del plan
    # contratado, no pago por uso plano como Scribe — no hay una tarifa única
    # y honesta para estimar en USD sin saber el plan del fundador. Se
    # registra el consumo real (caracteres) sin inventar un costo.
    record("elevenlabs", "tts", None, {"characters": characters}, path=path)


def record_voyage_call(model: str, tokens: int, path: Path | None = None) -> None:
    prior = _cumulative_voyage_tokens(path)
    cost = pricing.estimate_voyage_cost(model, tokens, prior)
    record("voyage", model, cost, {"tokens": tokens}, path=path)


def _read_all(path: Path | None) -> list[dict]:
    target = _target(path)
    if not target.exists():
        return []
    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [json.loads(line) for line in content.splitlines()]


def _cumulative_voyage_tokens(path: Path | None) -> int:
    return sum(e.get("tokens", 0) for e in _read_all(path) if e.get("vendor") == "voyage")


def recent(n: int = 100, path: Path | None = None) -> list[dict]:
    return _read_all(path)[-n:]


def usage_metrics(path: Path | None = None) -> dict:
    # Métricas reales de consumo por vendor (llamadas, tokens, caracteres,
    # duración) — a diferencia de `summarize()`, que resume dólares
    # estimados, esto suma directamente los campos que cada tipo de llamada
    # ya registra, sin convertir nada a costo.
    metrics: dict[str, dict] = {}
    for e in _read_all(path):
        m = metrics.setdefault(
            e["vendor"],
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "tokens": 0, "characters": 0, "duration_seconds": 0.0},
        )
        m["calls"] += 1
        m["input_tokens"] += e.get("input_tokens") or 0
        m["output_tokens"] += e.get("output_tokens") or 0
        m["tokens"] += e.get("tokens") or 0
        m["characters"] += e.get("characters") or 0
        m["duration_seconds"] += e.get("duration_seconds") or 0
    return metrics


def summarize(path: Path | None = None, recent_days: int = 7) -> dict:
    entries = _read_all(path)
    now = time.time()
    today_cutoff = now - 24 * 3600
    week_cutoff = now - recent_days * 24 * 3600

    def cost_since(cutoff: float) -> float:
        return sum(e["cost_usd"] for e in entries if e.get("cost_usd") is not None and e["timestamp"] >= cutoff)

    by_vendor: dict[str, float] = {}
    unknown_cost_calls = 0
    for e in entries:
        if e.get("cost_usd") is None:
            unknown_cost_calls += 1
            continue
        by_vendor[e["vendor"]] = by_vendor.get(e["vendor"], 0.0) + e["cost_usd"]

    return {
        "total_usd": sum(by_vendor.values()),
        "today_usd": cost_since(today_cutoff),
        "last_7_days_usd": cost_since(week_cutoff),
        "by_vendor_usd": by_vendor,
        "total_calls": len(entries),
        "calls_without_cost_estimate": unknown_cost_calls,
    }
