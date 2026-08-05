from snarf.specialists.finance.monthly_pnl import MonthlyPnLSpecialist


def test_compute_with_no_transactions():
    result = MonthlyPnLSpecialist().compute([])
    assert result == {"income": 0.0, "expenses_by_category": {}, "total_expenses": 0.0, "net": 0.0}


def test_compute_separates_income_from_expenses_by_category():
    transactions = [
        {"amount": 1000.0, "category": "ingresos por servicios"},
        {"amount": -150.0, "category": "oficina"},
        {"amount": -50.0, "category": "oficina"},
        {"amount": -30.0, "category": "software"},
    ]
    result = MonthlyPnLSpecialist().compute(transactions)
    assert result["income"] == 1000.0
    assert result["expenses_by_category"] == {"oficina": -200.0, "software": -30.0}
    assert result["total_expenses"] == -230.0
    assert result["net"] == 770.0


def test_compute_uses_sin_categorizar_for_missing_category():
    transactions = [{"amount": -20.0}]
    result = MonthlyPnLSpecialist().compute(transactions)
    assert result["expenses_by_category"] == {"sin categorizar": -20.0}


def test_handle_returns_a_readable_summary():
    specialist = MonthlyPnLSpecialist()
    text = specialist.handle("pnl", {"transactions": [{"amount": 100.0, "category": "ingresos"}]})
    assert "Ingresos: 100.0" in text
