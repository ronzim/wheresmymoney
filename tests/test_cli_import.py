from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from wheresmymoney.categories import build_category_catalog
from wheresmymoney.cli_import import _format_import_error, run_import_pipeline
from wheresmymoney.deterministic_rules import (
    DeterministicRule,
    DeterministicRuleError,
    RuleApplication,
    RuleApplicationBatch,
)
from wheresmymoney.llm_categorizer import LLMCategorization, LLMCategorizationBatch
from wheresmymoney.models import Transaction
from wheresmymoney.runtime_config import RuntimeConfig
from wheresmymoney.sheet_writer import AppendResult
from wheresmymoney.target_config import TargetSheetConfig


@dataclass(frozen=True)
class DummyParsedStatement:
    source_bank: str
    transactions: tuple[Transaction, ...]
    parser_name: str


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(
        google_service_account_json=Path("config/service-account-google.json"),
        gemini_api_key="test-key",
        target_sheet_config_path=Path("config/target_sheet.example.json"),
        gemini_model="gemini-2.5-flash",
    )


def _target() -> TargetSheetConfig:
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
            "deterministic_rules_path": "config/deterministic_rules.example.json",
        }
    )


def _transaction(description: str, amount: str) -> Transaction:
    return Transaction(
        source_bank="Comune_bpm",
        transaction_date="21/04/2026",
        value_date="21/04/2026",
        amount=amount,
        currency="EUR",
        original_description=description,
    )


def test_run_import_pipeline_dry_run_retries_llm_and_preserves_order() -> None:
    original_transactions = (
        _transaction("stipendio aprile", "2000,00"),
        _transaction("spesa supermercato", "-34,50"),
    )
    catalog = build_category_catalog(["Categorie", "Entrate", "Spesa"], header_name="Categorie")
    captured_outputs: list[str] = []
    captured_review: list[tuple[Transaction, ...]] = []
    llm_attempts = {"count": 0}

    def parse_statement_func(_file_path: str | Path, _source_bank: str) -> DummyParsedStatement:
        return DummyParsedStatement(
            source_bank="Comune_bpm",
            transactions=original_transactions,
            parser_name="fake_parser",
        )

    def load_categories_func(_runtime: RuntimeConfig, _target: TargetSheetConfig):
        return catalog

    def load_rules_func(_file_path: str | Path, _catalog):
        return (DeterministicRule(contains="stipendio", category="Entrate"),)

    def apply_rules_func(transactions, rules):
        classified_transaction = Transaction(
            source_bank="Comune_bpm",
            transaction_date=date(2026, 4, 21),
            value_date=date(2026, 4, 21),
            amount=Decimal("2000.00"),
            currency="EUR",
            original_description="stipendio aprile",
            assigned_category=rules[0].category,
        )
        return RuleApplicationBatch(
            classified=(
                RuleApplication(
                    transaction=classified_transaction,
                    matched_rule=rules[0],
                    classification_source="rule",
                ),
            ),
            unmatched=(transactions[1],),
        )

    def categorize_func(transactions, _catalog, _runtime):
        llm_attempts["count"] += 1
        if llm_attempts["count"] == 1:
            raise RuntimeError("temporary llm outage")
        return LLMCategorizationBatch(
            classified=(
                LLMCategorization(
                    transaction=Transaction(
                        source_bank="Comune_bpm",
                        transaction_date=date(2026, 4, 21),
                        value_date=date(2026, 4, 21),
                        amount=Decimal("-34.50"),
                        currency="EUR",
                        original_description=transactions[0].original_description,
                        cleaned_description="Supermercato",
                        assigned_category="Spesa",
                    ),
                    classification_source="llm",
                    raw_response="{}",
                ),
            )
        )

    def review_func(transactions, _catalog, **_kwargs):
        captured_review.append(tuple(transactions))

        class Result:
            reviewed_transactions = tuple(transactions)
            confirmed = True

        return Result()

    def append_func(*_args, **_kwargs):
        raise AssertionError("append_func must not be called in dry-run")

    result = run_import_pipeline(
        "dummy.xlsx",
        "Comune_bpm",
        dry_run=True,
        llm_attempts=2,
        runtime_config=_runtime(),
        target_config=_target(),
        parse_statement_func=parse_statement_func,
        load_categories_func=load_categories_func,
        load_rules_func=load_rules_func,
        apply_rules_func=apply_rules_func,
        categorize_func=categorize_func,
        review_func=review_func,
        append_func=append_func,
        output_func=captured_outputs.append,
    )

    assert result.confirmed is True
    assert result.append_result is None
    assert result.rule_classified_count == 1
    assert result.llm_classified_count == 1
    assert llm_attempts["count"] == 2
    assert [item.original_description for item in captured_review[0]] == [
        "stipendio aprile",
        "spesa supermercato",
    ]
    assert captured_review[0][0].assigned_category == "Entrate"
    assert captured_review[0][1].assigned_category == "Spesa"


def test_run_import_pipeline_appends_after_confirmation() -> None:
    original_transactions = (_transaction("pagamento palestra", "-49,90"),)
    catalog = build_category_catalog(["Categorie", "Salute"], header_name="Categorie")

    def parse_statement_func(_file_path: str | Path, _source_bank: str) -> DummyParsedStatement:
        return DummyParsedStatement(
            source_bank="Comune_bpm",
            transactions=original_transactions,
            parser_name="fake_parser",
        )

    def load_categories_func(_runtime: RuntimeConfig, _target: TargetSheetConfig):
        return catalog

    def load_rules_func(_file_path: str | Path, _catalog):
        return ()

    def apply_rules_func(transactions, _rules):
        return RuleApplicationBatch(classified=(), unmatched=tuple(transactions))

    def categorize_func(transactions, _catalog, _runtime):
        return LLMCategorizationBatch(
            classified=(
                LLMCategorization(
                    transaction=Transaction(
                        source_bank="Comune_bpm",
                        transaction_date=date(2026, 4, 21),
                        value_date=date(2026, 4, 21),
                        amount=Decimal("-49.90"),
                        currency="EUR",
                        original_description=transactions[0].original_description,
                        cleaned_description="Palestra",
                        assigned_category="Salute",
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

    append_calls: list[tuple] = []

    def append_func(runtime, target, bank, reviewed_transactions):
        append_calls.append((runtime, target, bank, tuple(reviewed_transactions)))
        return AppendResult(
            worksheet_title=bank,
            start_row=42,
            row_count=len(reviewed_transactions),
            updated_range="A42:F42",
        )

    result = run_import_pipeline(
        "dummy.xlsx",
        "Comune_bpm",
        runtime_config=_runtime(),
        target_config=_target(),
        parse_statement_func=parse_statement_func,
        load_categories_func=load_categories_func,
        load_rules_func=load_rules_func,
        apply_rules_func=apply_rules_func,
        categorize_func=categorize_func,
        review_func=review_func,
        append_func=append_func,
        output_func=lambda _message: None,
    )

    assert result.confirmed is True
    assert result.append_result is not None
    assert result.append_result.updated_range == "A42:F42"
    assert len(append_calls) == 1
    assert append_calls[0][2] == "Comune_bpm"
    assert append_calls[0][3][0].assigned_category == "Salute"


def test_run_import_pipeline_falls_back_when_llm_is_still_unavailable() -> None:
    original_transactions = (_transaction("fornitore sconosciuto", "-12,00"),)
    catalog = build_category_catalog(["Categorie", "Spesa"], header_name="Categorie")
    reviewed_transactions: list[tuple[Transaction, ...]] = []

    def parse_statement_func(_file_path: str | Path, _source_bank: str) -> DummyParsedStatement:
        return DummyParsedStatement(
            source_bank="Comune_bpm",
            transactions=original_transactions,
            parser_name="fake_parser",
        )

    def load_categories_func(_runtime: RuntimeConfig, _target: TargetSheetConfig):
        return catalog

    def load_rules_func(_file_path: str | Path, _catalog):
        return ()

    def apply_rules_func(transactions, _rules):
        return RuleApplicationBatch(classified=(), unmatched=tuple(transactions))

    def categorize_func(_transactions, _catalog, _runtime):
        raise RuntimeError("provider unavailable")

    def review_func(transactions, _catalog, **_kwargs):
        reviewed_transactions.append(tuple(transactions))

        class Result:
            reviewed_transactions = tuple(transactions)
            confirmed = True

        return Result()

    result = run_import_pipeline(
        "dummy.xlsx",
        "Comune_bpm",
        dry_run=True,
        llm_attempts=2,
        runtime_config=_runtime(),
        target_config=_target(),
        parse_statement_func=parse_statement_func,
        load_categories_func=load_categories_func,
        load_rules_func=load_rules_func,
        apply_rules_func=apply_rules_func,
        categorize_func=categorize_func,
        review_func=review_func,
        append_func=lambda *_args, **_kwargs: None,
        output_func=lambda _message: None,
    )

    assert result.confirmed is True
    assert reviewed_transactions[0][0].assigned_category == "Da Verificare"
    assert reviewed_transactions[0][0].cleaned_description == "fornitore sconosciuto"


def test_run_import_pipeline_fails_on_rules_with_unknown_live_categories(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        '{"rules": ['
        '{"contains": "CASHBACK", "category": "Rimborsi"},'
        '{"contains": "STIPENDIO", "category": "Entrate"}'
        ']}'
    )
    original_transactions = (_transaction("stipendio aprile", "2000,00"),)

    target = TargetSheetConfig.from_dict(
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
            "deterministic_rules_path": str(rules_path),
        }
    )
    catalog = build_category_catalog(["Categorie", "Entrate"], header_name="Categorie")

    def parse_statement_func(_file_path: str | Path, _source_bank: str) -> DummyParsedStatement:
        return DummyParsedStatement(
            source_bank="Comune_bpm",
            transactions=original_transactions,
            parser_name="fake_parser",
        )

    def load_categories_func(_runtime: RuntimeConfig, _target: TargetSheetConfig):
        return catalog

    def categorize_func(_transactions, _catalog, _runtime):
        return LLMCategorizationBatch(classified=())

    def review_func(transactions, _catalog, **_kwargs):
        class Result:
            reviewed_transactions = tuple(transactions)
            confirmed = False

        return Result()

    with pytest.raises(
        DeterministicRuleError,
        match=r"contains='CASHBACK', category='Rimborsi'",
    ):
        run_import_pipeline(
            "dummy.xlsx",
            "Comune_bpm",
            dry_run=True,
            runtime_config=_runtime(),
            target_config=target,
            parse_statement_func=parse_statement_func,
            load_categories_func=load_categories_func,
            categorize_func=categorize_func,
            review_func=review_func,
            output_func=lambda _message: None,
        )


def test_format_import_error_prints_sorted_categories_one_per_line() -> None:
    error = DeterministicRuleError(
        "Unknown category in deterministic rule: contains='CASHBACK', category='Rimborsi'",
        available_categories=("spesa", "Animali", "Entrate"),
    )

    rendered = _format_import_error(error, use_color=False)

    assert rendered == (
        "Import fallito: Unknown category in deterministic rule: "
        "contains='CASHBACK', category='Rimborsi'\n"
        "Categorie disponibili nel foglio:\n"
        "- Animali\n"
        "- Entrate\n"
        "- spesa"
    )


def test_format_import_error_alternates_colors_for_categories() -> None:
    error = DeterministicRuleError(
        "Unknown category in deterministic rule: contains='CASHBACK', category='Rimborsi'",
        available_categories=("Entrate", "Animali", "Spesa"),
    )

    rendered = _format_import_error(error, use_color=True)

    assert "\033[96m- Animali\033[0m" in rendered
    assert "\033[93m- Entrate\033[0m" in rendered
    assert "\033[96m- Spesa\033[0m" in rendered