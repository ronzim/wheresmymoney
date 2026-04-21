from __future__ import annotations

from dataclasses import dataclass

import pytest

from wheresmymoney.models import Transaction
from wheresmymoney.sheet_writer import (
    SheetWriterError,
    append_transactions_to_sheet,
    build_append_rows,
    find_next_transaction_row,
)
from wheresmymoney.target_config import TargetSheetConfig


@dataclass
class FakeWorksheet:
    title: str
    values: list[list[str]]
    last_update_range: str | None = None
    last_update_values: list[list[str]] | None = None

    def get_all_values(self) -> list[list[str]]:
        return self.values

    def update(self, range_name: str, values: list[list[str]], **kwargs: object) -> object:
        self.last_update_range = range_name
        self.last_update_values = values
        return {"updatedRange": range_name}


def _config() -> TargetSheetConfig:
    return TargetSheetConfig.from_dict(
        {
            "spreadsheet_id": "sheet-id",
            "categories_sheet_name": "Categorie",
            "allowed_bank_tabs": ["Comune_bpm"],
            "protected_analysis_tabs": ["Categorie", "Andamento"],
            "transaction_start_row": 16,
            "bank_tab_columns": [
                "Data Valuta",
                "Importo",
                "Divisa",
                "Cat",
                "Descrizione",
            ],
        }
    )


def _transaction() -> Transaction:
    return Transaction(
        source_bank="Comune_bpm",
        transaction_date="01/02/2026",
        value_date="01/02/2026",
        amount="-16,00",
        currency="EUR",
        original_description="pagamento con carta",
        assigned_category="Regali",
    )


def test_find_next_transaction_row_uses_existing_data_block() -> None:
    sheet_values = [
        [], [], [], [], [], [], [], [], [], [], [], [],
        ["12", "€ 0,00"],
        [],
        ["Mese", "Data Valuta", "Importo", "Divisa", "Cat", "Descrizione"],
        ["2", "01/02/2026", "-16", "EUR", "Regali", "pagamento 1"],
        ["2", "01/02/2026", "-3,57", "EUR", "Regali", "pagamento 2"],
    ]

    assert find_next_transaction_row(sheet_values, 16, "with_month_formula") == 18


def test_build_append_rows_includes_month_formula_when_needed() -> None:
    rows = build_append_rows([_transaction()], 18, _config(), "with_month_formula")

    assert rows == [[
        "=MONTH(B18)",
        "01/02/2026",
        "-16,00",
        "EUR",
        "Regali",
        "pagamento con carta",
    ]]


def test_append_transactions_to_sheet_updates_expected_range() -> None:
    worksheet = FakeWorksheet(
        title="Comune_bpm",
        values=[
            [], [], [], [], [], [], [], [], [], [], [], [],
            ["12", "€ 0,00"],
            [],
            ["Mese", "Data Valuta", "Importo", "Divisa", "Cat", "Descrizione"],
            ["2", "01/02/2026", "-16", "EUR", "Regali", "pagamento 1"],
        ],
    )

    result = append_transactions_to_sheet(worksheet, [_transaction()], _config())

    assert result.start_row == 17
    assert result.updated_range == "A17:F17"
    assert worksheet.last_update_values == [[
        "=MONTH(B17)",
        "01/02/2026",
        "-16,00",
        "EUR",
        "Regali",
        "pagamento con carta",
    ]]


def test_append_transactions_to_sheet_rejects_protected_or_unknown_layout() -> None:
    worksheet = FakeWorksheet(
        title="Comune_bpm",
        values=[[], [], [], [], [], [], [], [], [], [], [], [], [], [], ["Header sbagliato"]],
    )

    with pytest.raises(SheetWriterError):
        append_transactions_to_sheet(worksheet, [_transaction()], _config())