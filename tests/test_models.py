from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wheresmymoney.models import Transaction, TransactionError, normalize_amount


def test_transaction_normalizes_core_fields() -> None:
    transaction = Transaction(
        source_bank="Comune_bpm",
        transaction_date="14/04/2026",
        value_date="2026-04-15",
        amount="1.234,56",
        currency="eur",
        original_description="  Pagamento POS supermercato  ",
        cleaned_description="Supermercato",
        assigned_category="Spesa",
    )

    assert transaction.transaction_date == date(2026, 4, 14)
    assert transaction.value_date == date(2026, 4, 15)
    assert transaction.amount == Decimal("1234.56")
    assert transaction.currency == "EUR"
    assert transaction.original_description == "  Pagamento POS supermercato  "
    assert transaction.effective_description == "Supermercato"


def test_normalize_amount_keeps_signed_value() -> None:
    assert normalize_amount("-12,34") == Decimal("-12.34")
    assert normalize_amount(15) == Decimal("15.00")


def test_transaction_rejects_missing_description() -> None:
    with pytest.raises(TransactionError):
        Transaction(
            source_bank="Lisa",
            transaction_date="14/04/2026",
            value_date="14/04/2026",
            amount="10,00",
            currency="EUR",
            original_description="",
        )


def test_transaction_export_excludes_mese() -> None:
    transaction = Transaction(
        source_bank="Lisa",
        transaction_date="14/04/2026",
        value_date="14/04/2026",
        amount="10,00",
        currency="EUR",
        original_description="Bonifico",
        assigned_category="Entrate",
    )

    with pytest.raises(TransactionError):
        transaction.to_sheet_row(["Mese", "Data Valuta", "Importo"])


def test_transaction_exports_known_sheet_columns() -> None:
    transaction = Transaction(
        source_bank="Mattia",
        transaction_date="14/04/2026",
        value_date="15/04/2026",
        amount="-42,50",
        currency="EUR",
        original_description="Pagamento carta originale",
        cleaned_description="Pagamento carta pulita",
        assigned_category="Svago",
    )

    assert transaction.to_sheet_row(
        ["Data Valuta", "Importo", "Divisa", "Cat", "Descrizione"]
    ) == [
        "15/04/2026",
        "-42.50",
        "EUR",
        "Svago",
        "Pagamento carta originale",
    ]