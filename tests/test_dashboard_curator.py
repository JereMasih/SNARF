from snarf.specialists.dashboard_curator import DashboardCuratorSpecialist


class _FakeLLM:
    def __init__(self, available=True, text=""):
        self.available = available
        self._text = text
        self.calls = 0

    def generate(self, system, messages):
        self.calls += 1
        return _FakeResponse(self._text)


class _FakeResponse:
    def __init__(self, text):
        self.text = text


EMPTY_SNAPSHOT = {"summaries": [], "cost_alert": None, "recent_errors": []}


def _summary(node_id, detalle="real", score=10.0, size_tier="medium"):
    return {
        "node_id": node_id, "tier": "capability", "count_recent": 1, "count_total": 1,
        "last_timestamp": 1000.0, "last_detalle": detalle, "has_error_recent": False, "score": score,
        "size_tier": size_tier, "activity_buckets": [0] * 12,
    }


def test_cached_curation_returns_none_without_a_prior_refresh(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    specialist = DashboardCuratorSpecialist(lambda: EMPTY_SNAPSHOT, lambda: _FakeLLM(), "fundador")
    assert specialist.cached_curation() is None


def test_refresh_with_nothing_real_never_calls_the_llm(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: no debería usarse\n---\n")
    specialist = DashboardCuratorSpecialist(lambda: EMPTY_SNAPSHOT, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert llm.calls == 0
    assert "sin actividad" in curation["headline"].lower() or "nada" in curation["headline"].lower()
    assert curation["node_captions"] == {}
    assert curation["node_templates"] == {}


def test_refresh_persists_and_cached_curation_reads_it_back_without_calling_llm(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: tenés una cosa real pendiente\n---\ndrive: standard_wide | se movió un archivo real")
    snapshot = {"summaries": [_summary("drive")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    specialist.refresh()
    assert llm.calls == 1
    cached = specialist.cached_curation()
    assert cached["headline"] == "tenés una cosa real pendiente"
    assert cached["node_captions"]["drive"] == "se movió un archivo real"
    assert cached["node_templates"]["drive"] == "standard_wide"
    # cached_curation nunca vuelve a llamar al LLM.
    assert llm.calls == 1


def test_refresh_ignores_captions_for_node_ids_outside_the_real_snapshot(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    # El LLM "alucina" un node_id (trading) que nunca estuvo en los datos
    # reales que se le dieron — nunca debe aparecer en el resultado.
    llm = _FakeLLM(text="TITULAR: resumen\n---\ndrive: real\ntrading: inventado, no debería aparecer")
    snapshot = {"summaries": [_summary("drive")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert "trading" not in curation["node_captions"]
    assert "trading" not in curation["node_templates"]
    assert curation["node_captions"]["drive"] == "real"


def test_refresh_mentions_real_cost_alert_in_prompt(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    captured_prompts = []

    class _CapturingLLM(_FakeLLM):
        def generate(self, system, messages):
            captured_prompts.append(messages[0]["content"])
            return _FakeResponse("TITULAR: hay una alerta real\n---\n")

    cost_alert = {
        "node_id": "cost", "tier": "alert", "count_recent": 5, "count_total": 5, "last_timestamp": None,
        "last_detalle": "gasto de hoy: $5.00 (umbral $1.00)", "has_error_recent": False, "score": 100.0,
        "size_tier": "large", "cost_series": [1.0, 2.0, 5.0],
    }
    snapshot = {"summaries": [], "cost_alert": cost_alert, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: _CapturingLLM(), "fundador")
    specialist.refresh()
    assert "$5.00" in captured_prompts[0]


def test_refresh_without_llm_available_never_calls_generate_and_is_honest(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(available=False)
    snapshot = {"summaries": [_summary("drive")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert llm.calls == 0
    assert "modelo de lenguaje" in curation["headline"]


def test_handle_returns_the_headline_and_prefers_cache(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: resumen real\n---\n")
    snapshot = {"summaries": [_summary("drive")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    result = specialist.handle("¿qué hay en el dashboard?", {})
    assert result == "resumen real"
    assert llm.calls == 1
    # Segunda llamada usa el cache, no vuelve a pegarle al LLM.
    specialist.handle("¿qué hay en el dashboard?", {})
    assert llm.calls == 1


def test_refresh_parses_captions_even_when_llm_echoes_the_score_hint(tmp_path, monkeypatch):
    # Regresión de un comportamiento real observado con una llamada real al
    # LLM (v1): el modelo repite el "(score N.N)" que ya aparece en el
    # prompt de entrada, aunque el formato pedido sea "node_id: ..." a secas.
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(
        text=(
            "TITULAR: resumen real\n---\n"
            "drive (score 69.6): se movió un archivo real\n"
            "gmail_send (score 45.6, 3 eventos recientes): se mandó un mail real"
        )
    )
    snapshot = {"summaries": [_summary("drive"), _summary("gmail_send")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert curation["node_captions"]["drive"] == "se movió un archivo real"
    assert curation["node_captions"]["gmail_send"] == "se mandó un mail real"


def test_curation_is_isolated_per_user(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: real\n---\n")
    snapshot = {"summaries": [_summary("drive")], "cost_alert": None, "recent_errors": []}
    DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador").refresh()
    other = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "otro_usuario")
    assert other.cached_curation() is None


# --- v2: tamaño mecánico + variante elegida por el LLM + propuestas ---


def test_refresh_resolves_a_valid_template_id_within_its_tier(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: resumen\n---\ndrive: chart_caption | hay actividad real reciente")
    snapshot = {"summaries": [_summary("drive", size_tier="medium")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert curation["node_templates"]["drive"] == "chart_caption"
    assert curation["node_captions"]["drive"] == "hay actividad real reciente"


def test_refresh_falls_back_to_tier_default_when_template_id_is_from_the_wrong_tier(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    # "featured" es una plantilla GRANDE — inválida para un nodo mediano.
    llm = _FakeLLM(text="TITULAR: resumen\n---\ndrive: featured | caption real")
    snapshot = {"summaries": [_summary("drive", size_tier="medium")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert curation["node_templates"]["drive"] == "standard_wide"  # default mecánico de "medium"


def test_refresh_falls_back_to_tier_default_when_llm_omits_the_separator(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: resumen\n---\ndrive: caption real sin separador de plantilla")
    snapshot = {"summaries": [_summary("drive", size_tier="large")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert curation["node_templates"]["drive"] == "featured"  # default mecánico de "large"
    assert curation["node_captions"]["drive"] == "caption real sin separador de plantilla"


def test_refresh_curates_the_cost_node_with_its_own_template(tmp_path, monkeypatch):
    # v2: "cost" ya no es solo una línea de contexto aparte (v1) — es un
    # nodo curado como cualquier otro, con su propio tamaño/plantilla.
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    llm = _FakeLLM(text="TITULAR: hay una alerta real\n---\ncost: critical_alert | gasto real sobre el umbral")
    cost_alert = {
        "node_id": "cost", "tier": "alert", "count_recent": 5, "count_total": 5, "last_timestamp": None,
        "last_detalle": "gasto de hoy: $5.00 (umbral $1.00)", "has_error_recent": False, "score": 100.0,
        "size_tier": "large", "cost_series": [1.0, 2.0, 5.0],
    }
    snapshot = {"summaries": [], "cost_alert": cost_alert, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    curation = specialist.refresh()
    assert curation["node_templates"]["cost"] == "critical_alert"
    assert "umbral" in curation["node_captions"]["cost"]


def test_prompt_lists_the_valid_template_menu_for_each_nodes_tier(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    captured_prompts = []

    class _CapturingLLM(_FakeLLM):
        def generate(self, system, messages):
            captured_prompts.append(messages[0]["content"])
            return _FakeResponse("TITULAR: real\n---\n")

    snapshot = {"summaries": [_summary("drive", size_tier="medium")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: _CapturingLLM(), "fundador")
    specialist.refresh()
    prompt = captured_prompts[0]
    assert "[medium]" in prompt
    assert "MEDIUM:" in prompt
    assert "standard_wide" in prompt  # una de las 8 variantes medianas reales
    assert "featured" not in prompt  # plantilla GRANDE, no debería ofrecerse para un nodo mediano


def test_refresh_persists_template_proposals_for_founder_review(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(module, "TEMPLATE_PROPOSALS_PATH", tmp_path / "proposals.json")
    llm = _FakeLLM(
        text=(
            "TITULAR: resumen\n---\n"
            "drive: standard_wide | caption real\n"
            "PROPUESTA: comparativa_semanal: hace falta comparar 7 días reales, no solo hoy"
        )
    )
    snapshot = {"summaries": [_summary("drive", size_tier="medium")], "cost_alert": None, "recent_errors": []}
    specialist = DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador")
    specialist.refresh()
    proposals = module._load_template_proposals()
    assert len(proposals) == 1
    assert proposals[0]["name"] == "comparativa_semanal"
    assert "7 días" in proposals[0]["reason"]
    assert proposals[0]["user_id"] == "fundador"
    # Nunca se aplica sola: no aparece como una plantilla real utilizable.
    assert "comparativa_semanal" not in module.widget_templates.WIDGET_TEMPLATES
    assert "drive" in specialist.cached_curation()["node_templates"]


def test_template_proposals_list_is_capped_and_keeps_the_most_recent(tmp_path, monkeypatch):
    from snarf.specialists import dashboard_curator as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(module, "TEMPLATE_PROPOSALS_PATH", tmp_path / "proposals.json")
    proposal_lines = "\n".join(f"PROPUESTA: idea_{i}: motivo real {i}" for i in range(25))
    llm = _FakeLLM(text=f"TITULAR: resumen\n---\ndrive: standard_wide | caption real\n{proposal_lines}")
    snapshot = {"summaries": [_summary("drive", size_tier="medium")], "cost_alert": None, "recent_errors": []}
    DashboardCuratorSpecialist(lambda: snapshot, lambda: llm, "fundador").refresh()
    proposals = module._load_template_proposals()
    assert len(proposals) == module.MAX_STORED_TEMPLATE_PROPOSALS
    assert proposals[-1]["name"] == "idea_24"  # se conservan las más recientes
