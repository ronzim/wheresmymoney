from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import mkdtemp

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
        checkpoint_dir=Path(mkdtemp(prefix="wmm-test-checkpoints-")),
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


def test_run_import_pipeline_reports_checkpoint_resume() -> None:
    original_transactions = (_transaction("pagamento palestra", "-49,90"),)
    catalog = build_category_catalog(["Categorie", "Salute"], header_name="Categorie")
    captured_outputs: list[str] = []

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

    def append_func(_runtime, _target, bank, reviewed_transactions):
        return AppendResult(
            worksheet_title=bank,
            start_row=42,
            row_count=0,
            updated_range="",
            skipped_existing_count=len(reviewed_transactions),
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
        output_func=captured_outputs.append,
    )

    assert result.confirmed is True
    assert captured_outputs[-2] == (
        "Checkpoint rilevato: 1 transazioni gia' presenti su Comune_bpm."
    )
    assert captured_outputs[-1] == (
        "Ripresa completata: nessuna nuova riga da scrivere su Comune_bpm."
    )


def test_run_import_pipeline_checkpoint_preserves_unreviewed_transactions(
    tmp_path: Path,
) -> None:
    """Verifica che il checkpoint salvi sempre tutte le transazioni (revisionate +
    rimanenti), non solo quelle già viste. Riproduce il bug per cui dopo un'interruzione
    a 2/5 il checkpoint riportava 2/2, perdendo le ultime 3."""
    runtime = RuntimeConfig(
        google_service_account_json=Path("config/service-account-google.json"),
        gemini_api_key="test-key",
        target_sheet_config_path=Path("config/target_sheet.example.json"),
        gemini_model="gemini-2.5-flash",
        checkpoint_dir=tmp_path / "checkpoints",
    )
    target = _target()
    saved_checkpoints: list[tuple[tuple[Transaction, ...], int]] = []

    original_transactions = tuple(
        _transaction(f"movimento {i}", f"-{i*10},00") for i in range(1, 6)
    )
    catalog = build_category_catalog(
        ["Categorie", "Spesa"],
        header_name="Categorie",
    )

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
            classified=tuple(
                LLMCategorization(
                    transaction=Transaction(
                        source_bank="Comune_bpm",
                        transaction_date=date(2026, 4, 21),
                        value_date=date(2026, 4, 21),
                        amount=t.amount,
                        currency="EUR",
                        original_description=t.original_description,
                        assigned_category="Spesa",
                    ),
                    classification_source="llm",
                    raw_response="{}",
                )
                for t in transactions
            )
        )

    progress_calls: list[tuple[tuple[Transaction, ...], int]] = []

    def review_func(transactions, _catalog, **kwargs):
        on_progress = kwargs.get("on_review_progress")
        initial = kwargs.get("initial_reviewed_count", 0)
        # simula revisione di 2 transazioni e poi interruzione
        reviewed: list[Transaction] = list(transactions[:initial])
        for offset in range(initial, min(initial + 2, len(transactions))):
            reviewed.append(transactions[offset])
            if on_progress:
                on_progress(tuple(reviewed), len(reviewed))
                progress_calls.append((tuple(reviewed), len(reviewed)))

        class Result:
            reviewed_transactions = tuple(reviewed)
            confirmed = False

        return Result()

    run_import_pipeline(
        "dummy.xlsx",
        "Comune_bpm",
        runtime_config=runtime,
        target_config=target,
        parse_statement_func=parse_statement_func,
        load_categories_func=load_categories_func,
        load_rules_func=load_rules_func,
        apply_rules_func=apply_rules_func,
        categorize_func=categorize_func,
        review_func=review_func,
        append_func=lambda *_args, **_kwargs: None,
        output_func=lambda _message: None,
    )

    # il checkpoint deve avere TUTTE e 5 le transazioni, non solo le 2 viste
    from wheresmymoney.import_checkpoint import load_import_checkpoint
    cp = load_import_checkpoint(runtime.checkpoint_dir, "dummy.xlsx", "Comune_bpm")
    assert cp is not None
    assert len(cp.transactions) == 5
    assert cp.reviewed_count == 2
    # le prime 2 sono revisionate, le ultime 3 mantengono le categorie automatiche
    assert all(t.assigned_category is not None for t in cp.transactions)


def test_run_import_pipeline_resumes_from_local_checkpoint(tmp_path: Path) -> None:
    runtime = RuntimeConfig(
        google_service_account_json=Path("config/service-account-google.json"),
        gemini_api_key="test-key",
        target_sheet_config_path=Path("config/target_sheet.example.json"),
        gemini_model="gemini-2.5-flash",
        checkpoint_dir=tmp_path / "checkpoints",
    )
    target = _target()
    captured_outputs: list[str] = []
    reviewed_inputs: list[tuple[Transaction, ...]] = []
    reviewed_counts: list[int] = []
    checkpoint_transactions = (
        Transaction(
            source_bank="Comune_bpm",
            transaction_date="21/04/2026",
            value_date="21/04/2026",
            amount="-10,00",
            currency="EUR",
            original_description="gia classificata",
            assigned_category="Spesa",
        ),
        Transaction(
            source_bank="Comune_bpm",
            transaction_date="22/04/2026",
            value_date="22/04/2026",
            amount="-20,00",
            currency="EUR",
            original_description="ancora da rivedere",
            assigned_category="Spesa",
        ),
    )

    from wheresmymoney.import_checkpoint import ImportCheckpoint, save_import_checkpoint

    save_import_checkpoint(
        runtime.checkpoint_dir,
        ImportCheckpoint(
            file_path=str((tmp_path / "dummy.xlsx").resolve()),
            source_bank="Comune_bpm",
            parser_name="fake_parser",
            rule_classified_count=1,
            llm_classified_count=1,
            reviewed_count=1,
            transactions=checkpoint_transactions,
        ),
    )

    def parse_statement_func(_file_path: str | Path, _source_bank: str) -> DummyParsedStatement:
        raise AssertionError("parse_statement_func must not be called when resuming")

    def load_categories_func(_runtime: RuntimeConfig, _target: TargetSheetConfig):
        return build_category_catalog(["Categorie", "Spesa"], header_name="Categorie")

    def load_rules_func(_file_path: str | Path, _catalog):
        raise AssertionError("load_rules_func must not be called when resuming")

    def apply_rules_func(_transactions, _rules):
        raise AssertionError("apply_rules_func must not be called when resuming")

    def categorize_func(_transactions, _catalog, _runtime):
        raise AssertionError("categorize_func must not be called when resuming")

    def review_func(transactions, _catalog, **kwargs):
        reviewed_inputs.append(tuple(transactions))
        reviewed_counts.append(kwargs["initial_reviewed_count"])

        class Result:
            reviewed_transactions = tuple(transactions)
            confirmed = False

        return Result()

    result = run_import_pipeline(
        tmp_path / "dummy.xlsx",
        "Comune_bpm",
        runtime_config=runtime,
        target_config=target,
        parse_statement_func=parse_statement_func,
        load_categories_func=load_categories_func,
        load_rules_func=load_rules_func,
        apply_rules_func=apply_rules_func,
        categorize_func=categorize_func,
        review_func=review_func,
        append_func=lambda *_args, **_kwargs: None,
        output_func=captured_outputs.append,
    )

    assert result.confirmed is False
    assert reviewed_counts == [1]
    assert reviewed_inputs == [checkpoint_transactions]
    assert captured_outputs[0] == (
        "Checkpoint locale trovato: ripresa review da 1/2 transazioni."
    )


def test_run_import_pipeline_passes_all_unmatched_transactions_to_llm_once() -> None:
    original_transactions = (
        _transaction("spesa supermercato", "-34,50"),
        _transaction("benzina", "-60,00"),
        _transaction("ristorante", "-25,00"),
    )
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Auto", "Svago"],
        header_name="Categorie",
    )
    categorize_calls: list[tuple[Transaction, ...]] = []

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
        categorize_calls.append(tuple(transactions))
        categories = ("Spesa", "Auto", "Svago")
        cleaned = ("Supermercato", "Carburante", "Ristorante")
        classified = []
        for transaction, category, cleaned_description in zip(
            transactions,
            categories,
            cleaned,
        ):
            classified.append(
                LLMCategorization(
                    transaction=Transaction(
                        source_bank="Comune_bpm",
                        transaction_date=date(2026, 4, 21),
                        value_date=date(2026, 4, 21),
                        amount=transaction.amount,
                        currency="EUR",
                        original_description=transaction.original_description,
                        cleaned_description=cleaned_description,
                        assigned_category=category,
                    ),
                    classification_source="llm",
                    raw_response="{}",
                )
            )
        return LLMCategorizationBatch(classified=tuple(classified))

    def review_func(transactions, _catalog, **_kwargs):

        class Result:
            reviewed_transactions = tuple(transactions)
            confirmed = True

        return Result()

    result = run_import_pipeline(
        "dummy.xlsx",
        "Comune_bpm",
        dry_run=True,
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

    assert result.llm_classified_count == 3
    assert len(categorize_calls) == 1
    assert [item.original_description for item in categorize_calls[0]] == [
        "spesa supermercato",
        "benzina",
        "ristorante",
    ]


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