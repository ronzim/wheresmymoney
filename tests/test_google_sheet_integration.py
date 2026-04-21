from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import gspread
import pytest

from wheresmymoney.categories import build_category_catalog
from wheresmymoney.cli_import import run_import_pipeline
from wheresmymoney.deterministic_rules import RuleApplicationBatch
from wheresmymoney.llm_categorizer import LLMCategorization, LLMCategorizationBatch
from wheresmymoney.models import Transaction
from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError
from wheresmymoney.target_config import TargetSheetConfig, TargetSheetConfigError


@dataclass(frozen=True)
class DummyParsedStatement:
    source_bank: str
    transactions: tuple[Transaction, ...]
    parser_name: str


def test_run_import_pipeline_appends_to_live_google_sheet() -> None:
    runtime_config, target_config = _load_live_runtime_and_target()
    bank_tab = "Comune_bpm"
    marker = f"LIVE_INTEGRATION_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    original_transaction = Transaction(
        source_bank=bank_tab,
        transaction_date="21/04/2026",
        value_date="21/04/2026",
        amount="77,77",
        currency="EUR",
        original_description=marker,
    )

    def parse_statement_func(_file_path: str | Path, _source_bank: str) -> DummyParsedStatement:
        return DummyParsedStatement(
            source_bank=bank_tab,
            transactions=(original_transaction,),
            parser_name="integration_stub",
        )

    def load_categories_func(_runtime: RuntimeConfig, _target: TargetSheetConfig):
        return build_category_catalog(["Categorie", "Spesa"], header_name="Categorie")

    def load_rules_func(_file_path: str | Path, _catalog):
        return ()

    def apply_rules_func(transactions, _rules):
        return RuleApplicationBatch(classified=(), unmatched=tuple(transactions))

    def categorize_func(transactions, _catalog, _runtime):
        return LLMCategorizationBatch(
            classified=(
                LLMCategorization(
                    transaction=replace(
                        transactions[0],
                        assigned_category="Spesa",
                        cleaned_description="Integrazione live",
                    ),
                    classification_source="llm",
                    raw_response="{}",
                ),
            )
        )

    def review_func(transactions, _catalog, **_kwargs):
        class Result:
            reviewed_transactions = tuple(transactions)
            confirmed = True

        return Result()

    result = run_import_pipeline(
        "dummy.xlsx",
        bank_tab,
        runtime_config=runtime_config,
        target_config=target_config,
        parse_statement_func=parse_statement_func,
        load_categories_func=load_categories_func,
        load_rules_func=load_rules_func,
        apply_rules_func=apply_rules_func,
        categorize_func=categorize_func,
        review_func=review_func,
        output_func=lambda _message: None,
    )

    assert result.append_result is not None
    assert result.append_result.worksheet_title == bank_tab

    client = gspread.service_account(filename=str(runtime_config.google_service_account_json))
    worksheet = client.open_by_key(target_config.spreadsheet_id).worksheet(bank_tab)
    row_number = result.append_result.start_row
    formula_view = worksheet.get(
        f"A{row_number}:F{row_number}",
        value_render_option="FORMULA",
    )
    display_view = worksheet.get(f"A{row_number}:F{row_number}")

    assert formula_view
    assert display_view
    assert formula_view[0][0] == f"=MONTH(B{row_number})"
    assert display_view[0][1] == "21/04/2026"
    assert display_view[0][2] == "77,77"
    assert display_view[0][3] == "EUR"
    assert display_view[0][4] == "Spesa"
    assert display_view[0][5] == marker


def _load_live_runtime_and_target() -> tuple[RuntimeConfig, TargetSheetConfig]:
    if os.getenv("WHERESMYMONEY_RUN_LIVE_TESTS") != "1":
        pytest.skip("Set WHERESMYMONEY_RUN_LIVE_TESTS=1 to enable live Google Sheets integration tests")

    try:
        runtime_config = RuntimeConfig.from_env(allow_missing_secrets=True)
        target_config = TargetSheetConfig.from_file(runtime_config.target_sheet_config_path)
    except (RuntimeConfigError, TargetSheetConfigError) as exc:
        pytest.skip(f"Live Google Sheets integration is not configured: {exc}")

    if runtime_config.google_service_account_json is None:
        pytest.skip("GOOGLE_SERVICE_ACCOUNT_JSON is required for live Google Sheets integration tests")

    return runtime_config, target_config