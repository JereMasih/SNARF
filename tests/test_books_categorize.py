from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.finance.books_categorize import BooksCategorizeSpecialist


class FakeDrive:
    def __init__(self, csv_text):
        self._csv_text = csv_text

    def read_file_text(self, file_id, mime_type):
        return self._csv_text


class FakeLLM:
    def __init__(self, available=True, response=""):
        self.available = available
        self._response = response
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        return LLMResponse(text=self._response, speech=self._response)


CSV_TWO_ROWS = "date,description,amount\n2026-08-01,Office chair,-150.00\n2026-08-02,Client payment,1000.00\n"


def make_specialist(csv_text=CSV_TWO_ROWS, llm=None):
    llm = llm or FakeLLM(response="1: oficina\n2: ingresos por servicios\n")
    return BooksCategorizeSpecialist(FakeDrive(csv_text), lambda: llm, "fundador"), llm


def test_categorize_with_empty_sheet_reports_no_transactions():
    specialist, llm = make_specialist(csv_text="")
    result = specialist.categorize("file-1")
    assert result["transaction_count"] == 0
    assert llm.calls == []


def test_categorize_without_llm_available_degrades_honestly():
    specialist, _ = make_specialist(llm=FakeLLM(available=False))
    result = specialist.categorize("file-1")
    assert "falta configurar" in result["note"].lower()
    assert result["transaction_count"] == 2
    assert all(t["category"] is None for t in result["transactions"])


def test_categorize_assigns_real_categories_by_index():
    specialist, _ = make_specialist()
    result = specialist.categorize("file-1")
    assert result["transactions"][0]["category"] == "oficina"
    assert result["transactions"][1]["category"] == "ingresos por servicios"


def test_categorize_unmatched_index_falls_back_to_sin_categorizar():
    specialist, _ = make_specialist(llm=FakeLLM(response="1: oficina\n"))
    result = specialist.categorize("file-1")
    assert result["transactions"][1]["category"] == "sin categorizar"


def test_handle_reports_transaction_count():
    specialist, _ = make_specialist()
    assert "2 transacciones categorizadas" in specialist.handle("categorizar", {"file_id": "file-1"})
