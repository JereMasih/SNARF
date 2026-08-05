from snarf.specialists.finance.transactions import Transaction, parse_transactions_csv


def test_parses_a_real_csv_with_english_headers():
    csv_text = "date,description,amount\n2026-08-01,Office supplies,-45.50\n2026-08-02,Client payment,1200.00\n"
    transactions = parse_transactions_csv(csv_text)
    assert transactions == [
        Transaction(date="2026-08-01", description="Office supplies", amount=-45.50),
        Transaction(date="2026-08-02", description="Client payment", amount=1200.00),
    ]


def test_parses_a_real_csv_with_spanish_headers():
    csv_text = "fecha,descripcion,monto\n2026-08-01,Insumos de oficina,-45.50\n"
    transactions = parse_transactions_csv(csv_text)
    assert transactions == [Transaction(date="2026-08-01", description="Insumos de oficina", amount=-45.50)]


def test_handles_amounts_with_currency_symbols_and_thousand_separators():
    csv_text = "date,description,amount\n2026-08-01,Big payment,\"$1,200.00\"\n"
    transactions = parse_transactions_csv(csv_text)
    assert transactions[0].amount == 1200.00


def test_skips_rows_with_an_unparseable_amount_without_crashing():
    csv_text = "date,description,amount\n2026-08-01,Fila rota,n/a\n2026-08-02,Fila buena,10.00\n"
    transactions = parse_transactions_csv(csv_text)
    assert len(transactions) == 1
    assert transactions[0].description == "Fila buena"


def test_skips_rows_missing_date_or_description():
    csv_text = "date,description,amount\n,Sin fecha,10.00\n2026-08-01,,10.00\n2026-08-01,Fila real,10.00\n"
    transactions = parse_transactions_csv(csv_text)
    assert len(transactions) == 1


def test_returns_empty_list_when_expected_columns_are_missing():
    csv_text = "col1,col2\na,b\n"
    assert parse_transactions_csv(csv_text) == []


def test_returns_empty_list_for_an_empty_csv():
    assert parse_transactions_csv("") == []
