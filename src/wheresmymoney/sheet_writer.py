from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import gspread

from wheresmymoney.models import Transaction
from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError
from wheresmymoney.target_config import TargetSheetConfig


class SheetWriterError(ValueError):
    pass


@dataclass(frozen=True)
class AppendResult:
    worksheet_title: str
    start_row: int
    row_count: int
    updated_range: str


class WorksheetLike(Protocol):
    title: str

    def get_all_values(self) -> list[list[str]]:
        ...

    def update(
        self,
        range_name: str,
        values: list[list[str]],
        **kwargs: object,
    ) -> object:
        ...


def append_transactions_to_sheet(
    worksheet: WorksheetLike,
    transactions: list[Transaction] | tuple[Transaction, ...],
    target_config: TargetSheetConfig,
) -> AppendResult:
    if not transactions:
        raise SheetWriterError("No transactions to append")

    target_config.ensure_writable_tab(worksheet.title)
    sheet_values = worksheet.get_all_values()
    header_row_index = target_config.transaction_start_row - 1
    header = _get_header_row(sheet_values, header_row_index)

    write_mode = _resolve_write_mode(header, target_config.bank_tab_columns)
    next_row = find_next_transaction_row(
        sheet_values,
        target_config.transaction_start_row,
        write_mode,
    )
    payload = build_append_rows(transactions, next_row, target_config, write_mode)
    updated_range = build_update_range(next_row, len(payload), write_mode)

    worksheet.update(
        range_name=updated_range,
        values=payload,
        value_input_option="USER_ENTERED",
    )

    return AppendResult(
        worksheet_title=worksheet.title,
        start_row=next_row,
        row_count=len(payload),
        updated_range=updated_range,
    )


def append_transactions_via_gspread(
    runtime_config: RuntimeConfig,
    target_config: TargetSheetConfig,
    worksheet_title: str,
    transactions: list[Transaction] | tuple[Transaction, ...],
) -> AppendResult:
    if runtime_config.google_service_account_json is None:
        raise RuntimeConfigError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is required to append transactions"
        )

    client = gspread.service_account(
        filename=str(runtime_config.google_service_account_json)
    )
    worksheet = client.open_by_key(target_config.spreadsheet_id).worksheet(worksheet_title)
    return append_transactions_to_sheet(worksheet, transactions, target_config)


def find_next_transaction_row(
    sheet_values: list[list[str]],
    transaction_start_row: int,
    write_mode: str,
) -> int:
    first_data_column = 1 if write_mode == "with_month_formula" else 0
    last_non_empty_row = transaction_start_row - 1

    for row_index in range(transaction_start_row, len(sheet_values) + 1):
        row = sheet_values[row_index - 1]
        relevant_cells = row[first_data_column:]
        if any(cell.strip() for cell in relevant_cells if isinstance(cell, str)):
            last_non_empty_row = row_index

    return last_non_empty_row + 1


def build_append_rows(
    transactions: list[Transaction] | tuple[Transaction, ...],
    start_row: int,
    target_config: TargetSheetConfig,
    write_mode: str,
) -> list[list[str]]:
    payload: list[list[str]] = []
    amount_index = _find_amount_column_index(target_config.bank_tab_columns)

    for offset, transaction in enumerate(transactions):
        row_number = start_row + offset
        transaction_cells = transaction.to_sheet_row(target_config.bank_tab_columns)
        transaction_cells[amount_index] = _format_amount_for_sheet(
            transaction_cells[amount_index]
        )
        if write_mode == "with_month_formula":
            payload.append([f"=MONTH(B{row_number})", *transaction_cells])
        else:
            payload.append(transaction_cells)

    return payload


def build_update_range(start_row: int, row_count: int, write_mode: str) -> str:
    end_row = start_row + row_count - 1
    if write_mode == "with_month_formula":
        return f"A{start_row}:F{end_row}"
    return f"A{start_row}:E{end_row}"


def _get_header_row(sheet_values: list[list[str]], header_row_index: int) -> list[str]:
    if header_row_index < 1 or header_row_index > len(sheet_values):
        raise SheetWriterError("Header row is outside the current sheet bounds")
    return sheet_values[header_row_index - 1]


def _resolve_write_mode(
    header_row: list[str],
    configured_columns: tuple[str, ...],
) -> str:
    normalized_header = [cell.strip() for cell in header_row if isinstance(cell, str)]
    configured = list(configured_columns)

    if normalized_header[: len(configured)] == configured:
        return "direct"

    if normalized_header[: len(configured) + 1] == ["Mese", *configured]:
        return "with_month_formula"

    raise SheetWriterError(
        "Unexpected worksheet header for writer mapping: "
        f"{normalized_header}"
    )


def _find_amount_column_index(configured_columns: tuple[str, ...]) -> int:
    try:
        return list(configured_columns).index("Importo")
    except ValueError as exc:
        raise SheetWriterError("The target sheet config must include the 'Importo' column") from exc


def _format_amount_for_sheet(value: str) -> str:
    return value.replace(".", ",")