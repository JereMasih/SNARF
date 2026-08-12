import snarf.executive.specialist as specialist_module
from snarf.executive.specialist import ExecutiveBoardSpecialist
from snarf.runtime import agent_graph_registry


def _fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
    if role_config.role == "cfo":
        raise RuntimeError("proveedor caído")
    result = {"headline": f"{role_config.role} opina sobre: {question}", "opinions": [], "raw": ""}
    if upstream_context:
        result["received_upstream_context"] = upstream_context
    return result


def _board(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "CACHE_DIR", tmp_path / "executive_board")
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")
    return ExecutiveBoardSpecialist(llm_factory_for_role=lambda role: object())


def test_consult_runs_all_7_roles_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    result = board.consult("¿abrimos un canal de YouTube?")

    assert set(result["roles"].keys()) == {"cto", "coo", "research", "ceo", "cfo", "cmo", "creative"}
    assert result["roles"]["cto"]["headline"].startswith("cto opina")


def test_consult_restricts_to_the_requested_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    result = board.consult("pregunta técnica", roles=["cto"])

    assert set(result["roles"].keys()) == {"cto"}


def test_consult_rejects_an_unknown_role(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    result = board.consult("pregunta", roles=["cto", "not_a_real_role"])

    assert "error" in result
    assert "not_a_real_role" in result["error"]


def test_one_role_failing_never_takes_down_the_others(tmp_path, monkeypatch):
    # cfo explota adentro de _fake_consult_role — el resto del board tiene
    # que devolver su opinión real igual, nunca un fallo en cascada (ningún
    # rol depende de otro, Art. IV).
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    result = board.consult("pregunta", roles=["cto", "cfo"])

    assert "cto opina" in result["roles"]["cto"]["headline"]
    assert "proveedor caído" in result["roles"]["cfo"]["headline"]


def test_handle_returns_one_line_per_role(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    text = board.handle("pregunta", {"roles": ["cto", "coo"]})

    lines = text.splitlines()
    assert len(lines) == 2
    assert any(line.startswith("cto:") for line in lines)


def test_consult_persists_the_result_for_cached_consult(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    assert board.cached_consult() is None
    board.consult("pregunta", roles=["cto"])

    cached = board.cached_consult()
    assert cached["question"] == "pregunta"
    assert "cto" in cached["roles"]


# --- Motor de stages (Fase 17, ADR 0158) ------------------------------------


def test_consult_without_stages_configured_behaves_exactly_like_before(tmp_path, monkeypatch):
    # Sin ninguna versión guardada en agent_graph_registry, _stages_for()
    # debe devolver una única stage con los roles pedidos — mismo fan-out
    # 100% paralelo de siempre, ningún rol recibe upstream_context.
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)

    result = board.consult("pregunta", roles=["cto", "coo"])

    assert "received_upstream_context" not in result["roles"]["cto"]
    assert "received_upstream_context" not in result["roles"]["coo"]


def test_consult_with_stages_runs_a_later_stage_after_the_earlier_one(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)
    agent_graph_registry.save_new_version([["cto"], ["coo"]])

    result = board.consult("pregunta", roles=["cto", "coo"])

    assert "received_upstream_context" not in result["roles"]["cto"]
    assert "cto opina" in result["roles"]["coo"]["received_upstream_context"]


def test_consult_with_stages_never_drops_a_role_missing_from_the_saved_graph(tmp_path, monkeypatch):
    # El grafo guardado solo menciona a cto/coo — research se pidió también
    # y no aparece en ninguna stage: tiene que correr igual (stage extra).
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)
    agent_graph_registry.save_new_version([["cto"], ["coo"]])

    result = board.consult("pregunta", roles=["cto", "coo", "research"])

    assert set(result["roles"].keys()) == {"cto", "coo", "research"}


def test_consult_a_failed_role_never_gets_forwarded_as_upstream_context(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "consult_role", _fake_consult_role)
    board = _board(tmp_path, monkeypatch)
    agent_graph_registry.save_new_version([["cfo"], ["coo"]])

    result = board.consult("pregunta", roles=["cfo", "coo"])

    assert "proveedor caído" in result["roles"]["cfo"]["headline"]
    assert "received_upstream_context" not in result["roles"]["coo"]
