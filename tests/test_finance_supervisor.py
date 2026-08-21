from snarf.specialists.finance_supervisor import FinanceSupervisor


class FakeBooksCategorize:
    def __init__(self, result=None):
        self.calls = []
        self._result = result or {
            "transaction_count": 2,
            "transactions": [
                {"date": "2026-08-01", "description": "Cliente A", "amount": 1000.0, "category": "ingresos"},
                {"date": "2026-08-02", "description": "Software", "amount": -50.0, "category": "software"},
            ],
        }

    def categorize(self, file_id):
        self.calls.append(file_id)
        return self._result


class FakeMonthlyPnL:
    def __init__(self):
        self.calls = []

    def compute(self, transactions):
        self.calls.append(transactions)
        income = sum(t["amount"] for t in transactions if t["amount"] >= 0)
        expenses = sum(t["amount"] for t in transactions if t["amount"] < 0)
        return {
            "income": income,
            "expenses_by_category": {"software": expenses},
            "total_expenses": expenses,
            "net": income + expenses,
        }


class FakeLLM:
    def __init__(self, available=True, response="Análisis financiero real.", raise_error=False):
        self.available = available
        self._response = response
        self._raise_error = raise_error
        self.calls = []

    def generate(self, system, messages):
        self.calls.append({"system": system, "messages": messages})
        if self._raise_error:
            raise RuntimeError("fallo simulado")
        from snarf.capabilities.anthropic_llm import LLMResponse

        return LLMResponse(text=self._response, speech=self._response)


def make_supervisor(tmp_path, monkeypatch, llm_factory=None, books_categorize=None, monthly_pnl=None):
    monkeypatch.chdir(tmp_path)
    return FinanceSupervisor(
        books_categorize or FakeBooksCategorize(),
        monthly_pnl or FakeMonthlyPnL(),
        "fundador",
        llm_factory=llm_factory,
    )


def test_get_sheet_file_id_defaults_to_none(tmp_path, monkeypatch):
    supervisor = make_supervisor(tmp_path, monkeypatch)
    assert supervisor.get_sheet_file_id() is None


def test_set_and_get_sheet_file_id_roundtrip(tmp_path, monkeypatch):
    supervisor = make_supervisor(tmp_path, monkeypatch)
    supervisor.set_sheet_file_id("sheet-real-1")
    assert supervisor.get_sheet_file_id() == "sheet-real-1"


def test_sheet_file_id_is_namespaced_per_user(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    FinanceSupervisor(FakeBooksCategorize(), FakeMonthlyPnL(), "fundador").set_sheet_file_id("sheet-fundador")
    FinanceSupervisor(FakeBooksCategorize(), FakeMonthlyPnL(), "otro-usuario").set_sheet_file_id("sheet-otro")

    assert FinanceSupervisor(FakeBooksCategorize(), FakeMonthlyPnL(), "fundador").get_sheet_file_id() == "sheet-fundador"
    assert FinanceSupervisor(FakeBooksCategorize(), FakeMonthlyPnL(), "otro-usuario").get_sheet_file_id() == "sheet-otro"


def test_refresh_returns_none_without_a_configured_sheet(tmp_path, monkeypatch):
    supervisor = make_supervisor(tmp_path, monkeypatch)
    assert supervisor.refresh() is None


def test_refresh_computes_real_pnl_and_saves_snapshot(tmp_path, monkeypatch):
    books = FakeBooksCategorize()
    pnl = FakeMonthlyPnL()
    llm = FakeLLM(response="Neto positivo este período.")
    supervisor = make_supervisor(tmp_path, monkeypatch, llm_factory=lambda: llm, books_categorize=books, monthly_pnl=pnl)
    supervisor.set_sheet_file_id("sheet-1")

    snapshot = supervisor.refresh()

    assert books.calls == ["sheet-1"]
    assert snapshot["pnl"]["income"] == 1000.0
    assert snapshot["report"] == "Neto positivo este período."
    assert isinstance(snapshot["generated_at"], float)
    assert supervisor.get_snapshot() == snapshot
    # El contexto real mandado al LLM nunca inventa cifras — son las mismas
    # que devolvió el P&L determinístico.
    sent_content = llm.calls[0]["messages"][0]["content"]
    assert "1000.0" in sent_content or "1000" in sent_content


def test_refresh_without_llm_factory_says_so_explicitly(tmp_path, monkeypatch):
    supervisor = make_supervisor(tmp_path, monkeypatch)
    supervisor.set_sheet_file_id("sheet-1")
    snapshot = supervisor.refresh()
    assert "falta configurar el modelo de lenguaje" in snapshot["report"]


def test_refresh_degrades_gracefully_on_llm_error(tmp_path, monkeypatch):
    llm = FakeLLM(raise_error=True)
    supervisor = make_supervisor(tmp_path, monkeypatch, llm_factory=lambda: llm)
    supervisor.set_sheet_file_id("sheet-1")
    snapshot = supervisor.refresh()
    assert "No se pudo generar la interpretación" in snapshot["report"]


def test_get_snapshot_returns_none_before_any_refresh(tmp_path, monkeypatch):
    supervisor = make_supervisor(tmp_path, monkeypatch)
    assert supervisor.get_snapshot() is None
