import snarf.executive.specialist as specialist_module
from snarf.executive.specialist import ExecutiveBoardSpecialist


def _fake_consult_role(role_config, question, llm, repo_root):
    if role_config.role == "cfo":
        raise RuntimeError("proveedor caído")
    return {"headline": f"{role_config.role} opina sobre: {question}", "opinions": [], "raw": ""}


def _board(tmp_path, monkeypatch):
    monkeypatch.setattr(specialist_module, "CACHE_DIR", tmp_path / "executive_board")
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
