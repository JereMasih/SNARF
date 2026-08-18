from snarf.telemetry import leads


def test_append_and_list_all_roundtrip(tmp_path):
    path = tmp_path / "leads.jsonl"
    entry = leads.append("Ada", "ada@example.com", path=path)
    all_leads = leads.list_all(path=path)
    assert len(all_leads) == 1
    assert all_leads[0]["id"] == entry["id"]
    assert all_leads[0]["name"] == "Ada"
    assert all_leads[0]["email"] == "ada@example.com"


def test_list_all_sorts_newest_first(tmp_path):
    path = tmp_path / "leads.jsonl"
    leads.append("Primero", "primero@example.com", path=path)
    leads.append("Segundo", "segundo@example.com", path=path)
    names = [e["name"] for e in leads.list_all(path=path)]
    assert names == ["Segundo", "Primero"]


def test_list_all_with_no_file_is_empty(tmp_path):
    assert leads.list_all(path=tmp_path / "no_existe.jsonl") == []


def test_get_returns_none_for_a_missing_lead(tmp_path):
    path = tmp_path / "leads.jsonl"
    leads.append("Ada", "ada@example.com", path=path)
    assert leads.get("no-existe", path=path) is None


def test_get_returns_the_matching_lead(tmp_path):
    path = tmp_path / "leads.jsonl"
    entry = leads.append("Ada", "ada@example.com", path=path)
    assert leads.get(entry["id"], path=path) == entry
